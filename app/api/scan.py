"""
/scan-files endpoint returns details about record space files
/scan-status endpoint returns the status of async scan task
"""
import uuid
import json
import tempfile
import asyncio
import threading
import os

from helpers import parse_nextcloud_scan_xml, calculate_checksum
from flask import current_app, copy_current_request_context
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from config import Config
from abc import ABC, abstractmethod

from app.utils import files

# A dictionary to store the status of multiple tasks
tasks_status = {}


class DirectoryScanner(ABC):
    """Abstract base class for directory scanning."""

    @abstractmethod
    def fast_scan(self, dir_path: str):
        """Perform quick tasks scan of the given directory."""
        pass

    @abstractmethod
    async def slow_scan(self, dir_path: str):
        """Perform longer tasks scan of the given directory asynchronously."""
        pass


class FileManagerDirectoryScanner(DirectoryScanner):
    """Implements DirectoryScanner for the file manager."""

    def fast_scan(self, dir_path: str):
        """
        Implements a fast scan by interacting with Nextcloud's scan functionality.

        Args:
            dir_path (str): The directory path to be scanned.

        Returns:
            dict: The result of the fast scan parsed from the Nextcloud scan XML output.
        """
        scan_result = files.put_scandir(dir_path)
        return parse_nextcloud_scan_xml(scan_result)

    async def slow_scan(self, dir_path: str):
        """
        Implements a slow, thorough scan by calculating checksums of files on the disk.

        Args:
            dir_path (str): The directory path to be scanned.

        Returns:
            dict: A dictionary where keys are file paths and values are their checksums.
        """
        checksums = {}
        for dirpath, dirnames, filenames in os.walk(dir_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                checksums[file_path] = calculate_checksum(file_path)
        return checksums


class ScanFiles(Resource):
    """Resource to handle file scanning operations."""

    @jwt_required()
    def put(self, record_name):
        """
        Launch a file scanning process for a given record name. It performs a fast scan first and
        then launches an asynchronous slow scan.

        Args:
            record_name (str): The name of the record space to be scanned.

        Returns:
            tuple: A success response with the status code 200, or an error response with status code 500.
        """
        try:
            # Instantiate dirs
            parent_dir = f"mds2-{record_name}"
            system_dir = f"{parent_dir}/mds2-{record_name}-sys"
            record_space = f"{parent_dir}/mds2-{record_name}"
            root_dir_from_disk = Config.NEXTCLOUD_ROOT_DIR_PATH

            # Nextcloud scanning
            scanner = FileManagerDirectoryScanner()
            fast_scan_data = scanner.fast_scan(record_space)

            # Upload initial report
            filename = 'report.json'
            file_content = json.dumps({'nextcloud_scan': fast_scan_data}, indent=4)
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            try:
                # Write content as bytes
                temp_file.write(file_content.encode('utf-8'))
                # Go back to the beginning of the file
                temp_file.seek(0)
                files.post_file(temp_file.name, system_dir, filename)
            finally:
                # Close and delete the file
                temp_file.close()
                os.unlink(temp_file.name)

            # Create task for slow scan status updates
            task_id = str(uuid.uuid4())
            tasks_status[task_id] = {'Status': 'In Progress'}

            # Run the slowScan asynchronously using a thread
            @copy_current_request_context
            def run_slow_scan():
                with current_app.app_context():
                    # Read files from disk for performance
                    record_dir_from_disk = os.path.join(root_dir_from_disk, record_space)
                    checksums = asyncio.run(scanner.slow_scan(record_dir_from_disk))
                    tasks_status[task_id]['Checksums'] = checksums

                    # Update the report.json file after slow scan
                    report = {'nextcloud_scan': fast_scan_data, 'Checksums': checksums}
                    update_json_data = json.dumps(report, indent=4)
                    filepath = os.path.join(system_dir, filename)
                    files.put_file(update_json_data, filepath)
                    tasks_status[task_id]['Status'] = 'Completed'

            thread = threading.Thread(target=run_slow_scan)
            thread.start()

            success_response = {
                'success': 'PUT',
                'message': 'Scanning successfully started!',
                'task_id': task_id
            }

            return success_response, 200

        except IOError as e:
            return {'error': 'I/O Error', 'message': str(e)}, 500
        except Exception as e:
            return {'error': 'Unexpected Error', 'message': str(e)}, 500


class ScanStatus(Resource):
    """Resource to handle the retrieval of scanning task status."""

    @jwt_required()
    def get(self, task_id):
        """
        Retrieves the status of a scanning task using its unique task ID.

        Args:
            task_id (str): The unique identifier of the scanning task.

        Returns:
            tuple: The status of the scanning task if found with status code 200,
            otherwise an error message with status code 404.
        """
        task_status = tasks_status.get(task_id)
        if task_status:
            return task_status, 200
        else:
            return {'error': 'Not Found', 'message': 'Task ID not found!'}, 404
