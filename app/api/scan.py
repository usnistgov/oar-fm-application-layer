"""
/scans endpoint manages record space files scanning operations
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

# Global dictionary to keep track of scanning job statuses
scans_states = {}


class DirectoryScanner(ABC):
    """Abstract base class for directory scanning."""

    @abstractmethod
    def fast_scan(self, dir_path: str):
        """Abstract method to perform a quick scan of a directory."""
        pass

    @abstractmethod
    async def slow_scan(self, dir_path: str):
        """Abstract asynchronous method for a longer scan of a directory."""
        pass


class FileManagerDirectoryScanner(DirectoryScanner):
    """Implements DirectoryScanner for the file manager."""

    def fast_scan(self, dir_path: str):
        """
        Perform a fast scan using Nextcloud's scanning functionality.
        Parses the scan result from Nextcloud's XML output.

        Args:
            dir_path (str): Path of the directory to be scanned.

        Returns:
            dict: Parsed result of the fast scan.
        """
        scan_result = files.put_scandir(dir_path)
        return parse_nextcloud_scan_xml(scan_result)

    async def slow_scan(self, dir_path: str):
        """
        Perform a custom scan by calculating file checksums.
        This method is asynchronous and scans each file in the given directory.

        Args:
            dir_path (str): Path of the directory to be scanned.

        Returns:
            dict: Dictionary mapping file paths to their checksums.
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
            # Create task for this scanning task
            scan_id = str(uuid.uuid4())
            scans_states[scan_id] = {'Status': 'In Progress'}

            # Instantiate dirs
            parent_dir = record_name
            system_dir = f"{parent_dir}/{record_name}-sys"
            record_space = f"{parent_dir}/{record_name}"
            root_dir_from_disk = Config.NEXTCLOUD_ROOT_DIR_PATH

            # Nextcloud scanning
            scanner = FileManagerDirectoryScanner()
            fast_scan_data = scanner.fast_scan(record_space)

            # Update the scanning state
            scans_states[scan_id]['nextcloud_scan'] = fast_scan_data

            # Upload initial report
            filename = f"report-{scan_id}.json"
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

            # Run the slowScan asynchronously using a thread
            @copy_current_request_context
            def run_slow_scan():
                with current_app.app_context():
                    # Read files from disk for performance
                    record_dir_from_disk = os.path.join(root_dir_from_disk, record_space)
                    checksums = asyncio.run(scanner.slow_scan(record_dir_from_disk))
                    scans_states[scan_id]['Checksums'] = checksums

                    # Update the report.json file after slow scan
                    report = {'nextcloud_scan': fast_scan_data, 'Checksums': checksums}
                    update_json_data = json.dumps(report, indent=4)
                    filepath = os.path.join(system_dir, filename)
                    files.put_file(update_json_data, filepath)
                    scans_states[scan_id]['Status'] = 'Completed'

            thread = threading.Thread(target=run_slow_scan)
            thread.start()

            success_response = {
                'success': 'PUT',
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
            scan = scans_states.get(scan_id)

            if scan is not None:
                success_response = {
                    'success': 'GET',
                    'message': scan,
                }
                return success_response, 200
            return {'error': KeyError, 'message': f"Scanning '{scan_id}' Not Found"}, 404
        except Exception as e:
            return {'error': 'Unexpected Error', 'message': str(e)}, 500

    @jwt_required()
    def delete(self, scan_id):
        """
        Deletes a scanning task report and removes its record using its unique ID.

        Args:
            scan_id (str): Unique identifier of the scanning task.

        Returns:
            tuple: Success response with status code 200, or error response with status code 500.
        """
        try:
            del scans_states[scan_id]
            success_response = {
                'success': 'DELETE',
                'message': f"Scanning '{scan_id}' deleted successfully!",
            }
            return success_response, 200
        except KeyError:
            return {'error': 'Key Error!', 'message': f"Scanning '{scan_id}' Not Found"}, 404
