"""
/file endpoint manages files in a user record space
"""
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from flask import request

from app.utils import files


class File(Resource):
    @jwt_required()
    def post(self, destination_path=''):
        try:
            # Check if destination directory exists
            if len(destination_path) > 0 and not files.is_directory(destination_path):
                message = f"Directory '{destination_path}' does not exist!'"
                raise Exception(message)

            # Upload file
            file = request.files['file']
            files.post_file(file, destination_path)

            success_response = {
                'success': 'POST',
                'message': f"Created file '{file.filename}' in '{destination_path}' successfully!"
            }

            return success_response, 201

        except Exception as error:
            error_response = {
                'error': 'Bad Request',
                'message': str(error)
            }
            return error_response, 400
