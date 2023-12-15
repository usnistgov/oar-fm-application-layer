"""
/scans endpoint manages record space files scanning operations
"""
import uuid
import json
import tempfile
import asyncio
import threading
import datetime
import time
import re
import os

import helpers
from flask import current_app, copy_current_request_context
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from config import Config
from abc import ABC, abstractmethod
from pathlib import Path
from collections.abc import Mapping


from app.utils import files

# Global dictionary to keep track of scanning job statuses
scans_states = {}


class UserSpaceScanner(ABC):
    """
    the API for scanning a user space for application-specific purposes.

    From the perspective of this scanner, the user space is characterized by an identifier
    and two locally mounted filesystem directories: the "user" directory where
    the user has uploaded files, and the "system" directory where this scanner can
    read and write files not visible to the end-user.  When a scan is initiated, an
    implementation of this class is instantiated with these characteristics as properties,
    and then its :py:meth:`fast_scan` and :py:meth:`slow_scan` functions are called in that
    order.  Passed into these functions are the file-manager's metadata for the files (which
    can include subdirectories) that should be scanned.  Note that the slow_scan is called
    asynchronously (i.e. via the ``async`` keyword); however, :py:meth:`fast_scan` is
    guaranteed to be called before :py:meth:`slow_scan` is queued for the same set of files.

    The scanning functions are passed a dictionary of metadata that describe the files
    that should be scanned.  The top-level properties capture information about the set of
    files as a whole; the expected properties in this dictionary are as follows:

    ``space_id``
        str -- the identifier for the space
    ``scan_time``
        float -- the epoch time that the scan the produced this file listing was started.
    ``scan_datetime``
        str -- an ISO-formatted string form of the ``scan_time`` value (for display purposes)
    ``fm_space_path``
        str -- the file path of the user space from the file-manager perspective.  This is the
        path that a user would see as the location within the file-manager (nextcloud)
        application for the user's upload directory.
    ``contents``
        list -- an array of objects in which each object describes a file or subfolder within
        the user space.  (See file metadata properties below.)
    ``last_modified``
        str -- a formatted string marking the last time any file was modified in this record space.
    ``is_complete``
        bool -- True, if the contents represents a complete listing of all files and folders
        within the space.  If False, it is expected that the scannning functions will be called
        additional times with different sets of contents until the entire contents have been
        examined.

    The metadata may include additional top-level properties.  For example, it may include
    nextcloud properties describing the top level folder that is represents the user space.

    Each object in the ``contents`` list is a dictionary that describes a file or folder.  The
    following properties can be expected:

    ``fileid``
        str -- an identifier assigned by nextcloud for the file being described.
    ``path``
        str -- the path to the file or folder being described.  [This path will be the full
        path to the file and will start with the value of ``fm_space_path`` (defined above).]
    ``resource_type``
        str -- the type of this resource.  Allowed values are: "file", "collection"
    ``last_modified``
        str -- the formatted date-time marking the time the file was last modified
    ``size``
        int -- the size of the file in bytes
    ``scan_errors``
        list[str] -- a list of messages describing errors that occurred while scanning this file.

    Additional properties may be included.  For example, the file metadata may include nextcloud
    file properties for the file.

    The scanning functions can update any of this metadata in their returned version which will be
    made accessible to the client.

    See also the :py:class:`UserSpaceScannerBase` which can serve as a partially-implemented
    base class for a full implementation.
    """

    @property
    def space_id(self) -> str:
        """
        the identifier for the user space
        """
        raise NotImplementedError()

    @property
    def user_dir(self) -> Path:
        """
        the directory where the end-user has uploaded data.
        """
        raise NotImplementedError()

    @property
    def system_dir(self) -> Path:
        """
        the directory where this scanner can read and write files that are not visible
        to the end-user.
        """
        raise NotImplementedError()

    @abstractmethod
    def fast_scan(self, content_md: Mapping) -> Mapping:
        """
        synchronously examine a set of files specified by the given file metadata.

        The implementation should assume that this scanning was initiated via a web request
        that is waiting for this function to finish; thus, this function should return as
        quickly as possible.  Typically, an implementation would use this function to
        _initialize_ some information about the files and store that information under the
        system area.

        Typically, the files described in the input metadata will be the full set of files
        found in the user area.  However, a controller implementation (i.e. the implementation
        that calls this function) may choose to call this function for only a subset of the
        files in the space.  (For example, if the space contains a very large number of files,
        the controller may choose to split the full collection over a series of calls.)

        :param dict content_md:  the file-manager metadata describing the files to be
                                 examined.  See the
                                 :py:class:`class documentation<UserSpaceScanner>`
                                 for the schema of this metadata.
        :return:  the file-manager metadata that was passed in, possibly updated.
                  :rtype: dict
        """
        raise NotImplementedError()

    @abstractmethod
    async def slow_scan(self, content_md: Mapping) -> Mapping:
        """
        asynchronously examine a set of files specified by the given file metadata.

        For the set of files described in the input metadata, it is guaranteed that the
        :py:meth:`fast_scan` method has been called and returned its result.  If the
        :py:meth:`fast_scan` method updated the metadata, those updates should be
        included in the input metadata to this function.

        :param dict content_md:  the content metadata returned by the
                                 :py:meth:`fast_scan` method that describes the
                                 files that should be scanned.  See the
                                 :py:class:`class documentation<UserSpaceScanner>`
                                 for the schema of this metadata.
        :return:  the file-manager metadata that was passed in, possibly updated.
                  :rtype: dict
        """
        raise NotImplementedError()


class UserSpaceScannerBase(UserSpaceScanner, ABC):
    """
    a partial implementation of the :py:meth:`UserSpaceScanner` that can be used as a
    base class for full implementations.
    """

    def __init__(self, space_id: str, user_dir: Path, sys_dir: Path):
        """
        initialize the scanner.

        :param str  space_id:  the identifier for the user space that should be scanned
        :param Path user_dir:  the full path on a local filesystem to the directory where
                               the end-user has uploaded files.
        :param Path  sys_dir:  the full path on a local filesystem to a directory where
                               the scanner can read and write files that are not visible
                               to the end user.
        """
        self._id = space_id
        self._userdir = user_dir
        self._sysdir = sys_dir

    @property
    def space_id(self):
        return self._id

    @property
    def user_dir(self):
        return self._userdir

    @property
    def system_dir(self):
        return self._sysdir


class FileManagerDirectoryScanner(UserSpaceScannerBase):
    """
    an implementation of the :py:meth:`UserSpaceScanner` leveraging :py:meth:`UserSpaceScannerBase`
    for the file manager scanning operations.
    """

    def __init__(self, space_id: str, user_dir: Path, sys_dir: Path):
        super().__init__(space_id, user_dir, sys_dir)

    def fast_scan(self, content_md: Mapping) -> Mapping:
        scan_id = content_md['scan_id']
        fm_system_path = content_md['fm_system_path']

        # Upload initial report
        filename = f"report-{scan_id}.json"
        file_content = json.dumps(content_md, indent=4)
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        try:
            # Write content as bytes
            temp_file.write(file_content.encode('utf-8'))
            # Go back to the beginning of the file
            temp_file.seek(0)
            files.post_file(temp_file.name, str(fm_system_path), filename)
        finally:
            # Close and delete the file
            temp_file.close()
            os.unlink(temp_file.name)

        return content_md

    async def slow_scan(self, content_md: Mapping) -> Mapping:
        """
        Perform a custom scan by calculating file checksums if the file has been modified after
        the last checksum date (or there has never been a checksum calculated).
        This method is asynchronous and scans each file of the contents.

        Args:
            content_md (Mapping): Metadata describing the files to be scanned.

        Returns:
            Mapping:  The updated metadata with checksums added or updated for each file.
        """
        current_time = datetime.datetime.now()
        scan_id = content_md['scan_id']
        fm_system_path = content_md['fm_system_path']

        for resource in content_md['contents']:
            if resource['resource_type'] == 'file':
                last_modified = datetime.datetime.fromisoformat(resource['last_modified']).replace(tzinfo=None)
                last_checksum_date = datetime.datetime.fromisoformat(
                    resource.get('last_checksum_date', '1970-01-01T00:00:00')).replace(tzinfo=None)

                if last_modified > last_checksum_date:
                    file_path = resource['path']
                    checksum = helpers.calculate_checksum(file_path)
                    resource['checksum'] = checksum
                    resource['last_checksum_date'] = current_time.isoformat()

                    # Update the report.json file after each resource has been updated
                    update_json_data = json.dumps(content_md, indent=4)
                    filename = f"report-{scan_id}.json"
                    filepath = os.path.join(fm_system_path, filename)
                    files.put_file(update_json_data, filepath)

        return content_md


class ScanFiles(Resource):
    """Resource to handle file scanning operations."""

    @jwt_required()
    def post(self, record_name):
        """
        Starts a file scanning process for a specific record.
        Initiates a fast scan followed by an asynchronous slow scan.

        Args:
            record_name (str): Name of the record space to scan.

        Returns:
            tuple: Success response with status code 200, or error response with status code 500.
        """
        try:
            # Instantiate dirs
            space_id = record_name
            fm_system_path = Path(space_id) / f"{space_id}-sys"
            fm_space_path = Path(space_id) / f"{space_id}"
            root_dir_from_disk = Config.NEXTCLOUD_ROOT_DIR_PATH
            user_dir = os.path.join(root_dir_from_disk, fm_space_path)

            # Create task for this scanning task
            scan_id = str(uuid.uuid4())

            # Find current time
            current_epoch_time = time.time()

            # Find user space last modified file date
            nextcloud_dir_info = files.get_directory(fm_space_path)
            last_modified_date = helpers.find_last_modified(nextcloud_dir_info)

            # Convert epoch time to an ISO-formatted string
            current_datetime = datetime.datetime.fromtimestamp(current_epoch_time)
            display_time = current_datetime.isoformat()

            # Retrieve nextcloud metadata
            nextcloud_md = helpers.parse_nextcloud_scan_xml(fm_space_path, files.put_scandir(fm_space_path))

            # Instantiate content metadata
            contents = []
            for resource in nextcloud_md:
                fm_file_path = re.split(Config.API_USER, resource['path'], flags=re.IGNORECASE)[-1].lstrip('/')
                nextcloud_file_info = files.get_file(fm_file_path)
                resource_md = {
                    'fileid': resource['fileid'],
                    'path': os.path.join(root_dir_from_disk, fm_file_path),
                    'size': resource['size'],
                    'last_modified': helpers.find_last_modified(nextcloud_file_info),
                    'resource_type': helpers.determine_resource_type(resource),
                    'scan_errors': []
                }
                contents.append(resource_md)

            content_md = {
                'space_id': space_id,
                'scan_id': scan_id,
                'scan_time': current_epoch_time,
                'scan_datetime': display_time,
                'user_dir': str(user_dir),
                'fm_system_path': str(fm_system_path),
                'contents': contents,
                'last_modified': last_modified_date,
                'is_complete': True
            }

            # Instantiate Scanning Class
            scanner = FileManagerDirectoryScanner(space_id, fm_space_path, fm_system_path)

            # Run fast scanning and update metadata
            content_md = scanner.fast_scan(content_md)

            #TODO
            # Update the scanning state

            # Run the slowScan asynchronously using a thread
            @copy_current_request_context
            def run_slow_scan():
                with current_app.app_context():
                    # Read files from disk for performance
                    asyncio.run(scanner.slow_scan(content_md))

            thread = threading.Thread(target=run_slow_scan)
            thread.start()

            success_response = {
                'success': 'POST',
                'message': 'Scanning successfully started!',
                'scan_id': scan_id
            }

            return success_response, 200

        except IOError as e:
            return {'error': 'I/O Error', 'message': str(e)}, 500
        except Exception as e:
            return {'error': 'Unexpected Error', 'message': str(e)}, 500

    @jwt_required()
    def get(self, scan_id):
        """
        Retrieves the current state and details of a scanning task by its ID.

        Args:
            scan_id (str): Unique identifier of the scanning task.

        Returns:
            tuple: Scanning task status and content with status code 200, or error message with status code 404.
        """
        try:
            scan = scans_states[scan_id]

            if scan is not None:
                success_response = {
                    'success': 'GET',
                    'message': scan,
                }
                return success_response, 200
            return {'error': 'Key Error!', 'message': f"Scanning '{scan_id}' Not Found"}, 404
        except Exception as e:
            return {'error': 'Unexpected Error', 'message': str(e)}, 500

    @jwt_required()
    def delete(self, scan_id):
        """
        Deletes a scanning task report from the global dict and the file manager using its unique ID.

        Args:
            scan_id (str): Unique identifier of the scanning task.

        Returns:
            tuple: Success response with status code 200, or error response with status code 500.
        """
        try:
            file_path = scans_states[scan_id]['report_location']
            files.delete_file(file_path)
            del scans_states[scan_id]

            success_response = {
                'success': 'DELETE',
                'message': f"Scanning '{scan_id}' deleted successfully!",
            }
            return success_response, 200
        except KeyError:
            return {'error': 'Key Error!', 'message': f"Scanning '{scan_id}' Not Found"}, 404
        except Exception as e:
            return {'error': 'Unexpected Error', 'message': str(e)}, 500
