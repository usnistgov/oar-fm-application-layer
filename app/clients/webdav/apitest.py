"""
This module provides a client class, WebDAVClient, designed to perform WebDAV operations that interact with a Nextcloud instance to manage directories and files
"""
from webdav3.client import Client as WebDavClient
from webdav3.exceptions import WebDavException
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class WebDAVClient:
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
            path = f"{self.base_url}/remote.php/dav/files/{self.api_user}/{target.lstrip('/')}"

            if method == 'MKCOL':
                self.client.mkdir(path)
            elif method == 'PROPFIND':
                return self.client.info(path)
            elif method == 'DELETE':
                self.client.clean(path)
            elif method == 'PUT':
                if content is not None:
                    self.client.upload_sync(remote_path=path, local_path=None, content=content)
                else:
                    raise ValueError("Content must be provided to upload or modify a file!")
            elif method == 'GET':
                return self.client.download_sync(remote_path=path, local_path=None)
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


# Sample configuration
config = {
    'is_prod': False,
    'webdav_dev_url': 'http://localhost',
    'api_user': 'oar_api',
    'api_pwd': 'NISTnextcloudADMIN'
}

# Initialize WebDAV client
webdav_client = WebDAVClient(config)
r = webdav_client.client.list("/")
print(r)
r2 = webdav_client.client.list("/remote.php/dav/files/oar_api/")
print(r2)
# Create the target directory
target_directory_path = '/remote.php/dav/files/oar_api/files/oar_api/target/'
s = webdav_client.client.mkdir(target_directory_path)

print(f"Directory '{target_directory_path}' created successfully.")
