"""
This module provides a client class, WebDAVClient, designed to perform WebDAV operations that interact with a Nextcloud instance to manage directories and files
"""
from webdav3.client import Client as WebDavClient
from webdav3.exceptions import WebDavException
import logging
import tempfile
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class WebDAVApi:
    def __init__(self, config):
        self.is_prod = config['is_prod']
        self.api_user = config['api_user']
        if self.is_prod:
            self.base_url = config['webdav_prod_url']
        else:
            self.base_url = config['webdav_dev_url']
        self.client = WebDavClient({
            'webdav_hostname': self.base_url,
            'webdav_login': self.api_user,
            'webdav_password': config['api_pwd']
        })
        self.headers = {'Accept': 'application/json'}

    def handle_request(self, method, target, content=None):
        """ Generic request handler. """
        try:
            path = f"/remote.php/dav/files/{self.api_user}/{target.lstrip('/')}"
            if method == 'MKCOL':
                self.client.mkdir(path)
                logging.info(f"Directory created: {path}")
            elif method == 'PROPFIND':
                return self.client.info(path)
            elif method == 'DELETE':
                self.client.clean(path)
                logging.info(f"File/Folder deleted: {path}")
            elif method == 'PUT':
                if content is not None:
                    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.tmp') as temp_file:
                        temp_file.write(content)
                        temp_file_path = temp_file.name
                    self.client.upload_sync(remote_path=path, local_path=temp_file_path)
                    logging.info(f"File uploaded/modified: {path}")
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                else:
                    raise ValueError("Content must be provided to upload or modify a file!")
            elif method == 'GET':
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                self.client.download_sync(remote_path=path, local_path=temp_file.name)
                with open(temp_file.name, 'r', encoding='utf-8') as file:
                    content = file.read()
                    logging.info(f"File content retrieved: {content}")
                    temp_file.close()
                    os.remove(temp_file.name)
                return content
            else:
                raise ValueError(f"Unsupported method: {method}")
        except WebDavException as e:
            logging.error(f"WebDav error occurred while handling request: {e}")
            raise e
        except Exception as e:
            logging.error(f"Uncaught error occurred while handling request: {e}")
            raise e

    def create_directory(self, path):
        """ Create a directory given a path. """
        return self.handle_request('MKCOL', path)

    def get_directory_info(self, path):
        """ Get information on a directory given a path. """
        return self.handle_request('PROPFIND', path)

    def delete_directory(self, path):
        """ Delete a directory given a path. """
        return self.handle_request('DELETE', path)

    def upload_file(self, path, content):
        """ Post a file given its content and the path where to create it. """
        return self.handle_request('PUT', path, content)

    def get_file_info(self, path):
        """ Get information on a file given a path. """
        return self.handle_request('PROPFIND', path)

    def get_file_content(self, path):
        """ Get content of a file given a path. """
        return self.handle_request('GET', path)

    def delete_file(self, path):
        """ Delete a file given its path. """
        return self.handle_request('DELETE', path)

    def modify_file_content(self, path, new_content):
        """ Modify a file content given its path and new content. """
        return self.handle_request('PUT', path, new_content)