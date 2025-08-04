"""
/file endpoint manages files in a user record space
"""
import logging

from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

logging.basicConfig(level=logging.INFO)

from app.clients.webdav.api import WebDAVApi
import os
from config import Config


class File(Resource):
    @jwt_required()
    def post(self, destination_path=''):
        """Uploads a file to a specified directory path.
            This function handles uploading by accepting either a file path or a file object
        """
        try:
            webdav_client = WebDAVApi(Config)
            # Check if destination directory exists
            if len(destination_path) > 0 and not webdav_client.is_directory(destination_path):
                logging.error(f"Directory '{destination_path}' does not exist")
                return {'error': 'Not Found', 'message': f"Directory '{destination_path}' does not exist"}, 404

            # Check for file in request
            if 'file' not in request.files:
                logging.error("No file part in the request")
                return {'error': 'Bad Request', 'message': 'No file part in the request'}, 400

            # Upload file
            file = request.files['file']

            # Check for file name
            if file.filename == '':
                logging.error("No file selected for uploading")
                return {'error': 'Bad Request', 'message': 'No file selected for uploading'}, 400

            upload_response = webdav_client.upload_file(destination_path, file)

            if upload_response['status'] not in [200, 201, 204]:
                logging.error(f"Failed to upload file '{file.filename}'")
                return {'error': 'Internal Server Error', 'message': 'Failed to upload file'}, 500
            logging.info(f"Uploaded file '{file.filename}' to '{destination_path}'")

            success_response = {
                'success': 'POST',
                'message': f"Created file '{file.filename}' in '{destination_path}' successfully!"
            }

            return success_response, 201
        except Exception as error:
            logging.exception("An unexpected error occurred: " + str(error))
            return {"error": "Internal Server Error", "message": "An unexpected error occurred"}, 500

    @jwt_required()
    def delete(self, destination_path):
        """Deletes a file at a specified path."""
        try:
            webdav_client = WebDAVApi(Config)
            if not webdav_client.is_file(destination_path):
                logging.error(f"File '{destination_path}' not found")
                return {'error': 'File Not Found', 'message': 'File does not exist'}, 404

            delete_response = webdav_client.delete_file(destination_path)

            if delete_response['status'] not in [200, 204]:
                logging.error(f"Failed to delete file '{destination_path}'")
                return {'error': 'Internal Server Error', 'message': 'Failed to delete file'}, 500

            logging.info(f"Deleted file '{destination_path}'")
            return {'success': 'DELETE', 'message': f'File successfully deleted!'}, 200

        except Exception as error:
            logging.exception("An unexpected error occurred: " + str(error))
            return {"error": "Internal Server Error", "message": "An unexpected error occurred"}, 500
