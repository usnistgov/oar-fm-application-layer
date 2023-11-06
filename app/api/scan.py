"""
/scan-files endpoint returns details about record space files
/scan-status endpoint returns the status of async scan task
"""
import uuid
import json
import asyncio
import threading

from helpers import parse_nextcloud_scan_xml, calculate_checksum
import os
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from config import Config
from abc import ABC, abstractmethod

from app.utils import files

# A dictionary to store the status of multiple tasks
tasks_status = {}


class DirectoryScanner(ABC):

    @abstractmethod
    def fast_scan(self, dir_path: str):
        pass

    @abstractmethod
    async def slow_scan(self, dir_path: str):
        pass


class FileManagerDirectoryScanner(DirectoryScanner):

    def fast_scan(self, dir_path: str):
        scan_result = files.put_scandir(dir_path)
        return parse_nextcloud_scan_xml(scan_result)

    async def slow_scan(self, dir_path: str):
        checksums = {}
        for dirpath, dirnames, filenames in os.walk(dir_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                checksums[file_path] = calculate_checksum(file_path)
        return checksums


class ScanFiles(Resource):
    @jwt_required()
    def put(self, record_name):
        try:
            # Instantiate dirs
            parent_dir = f"mds2-{record_name}"
            system_dir = f"{parent_dir}/mds2-{record_name}-sys"
            record_space = f"{parent_dir}/mds2-{record_name}"

            scanner = FileManagerDirectoryScanner()
            fast_scan_data = scanner.fast_scan(record_space)

            root_dir = Config.NEXTCLOUD_ROOT_DIR_PATH
            system_dir = os.path.join(root_dir, system_dir)

            filename = 'report.json'
            filepath = os.path.join(system_dir, filename)

            with open(filepath, 'w') as file:
                json.dump({'nextcloud_scan': fast_scan_data}, file, indent=4)

            task_id = str(uuid.uuid4())
            tasks_status[task_id] = {'Status': 'In Progress'}
            record_fullpath = os.path.join(root_dir, record_space)

            # Run the slowScan asynchronously using a thread
            def run_slow_scan():
                checksums = asyncio.run(scanner.slow_scan(record_fullpath))
                tasks_status[task_id]['Checksums'] = checksums
                tasks_status[task_id]['Status'] = 'Completed'

                # Update the report.json file after slow scan
                report = {'nextcloud_scan': fast_scan_data, 'Checksums': checksums}
                with open(filepath, 'w') as file:
                    json.dump(report, file, indent=4)

            thread = threading.Thread(target=run_slow_scan)
            thread.start()

            success_response = {
                'success': 'PUT',
                'message': 'Scanning successfully started!',
                'task_id': task_id
            }

            return success_response, 200

        except Exception as error:
            error_response = {
                'error': 'Bad Request',
                'message': str(error)
            }
            return error_response, 400


class ScanStatus(Resource):

    @jwt_required()
    def get(self, task_id):
        task_status = tasks_status.get(task_id)
        if task_status:
            return task_status, 200
        else:
            return {'error': 'Not Found', 'message': 'Task ID not found!'}, 404
