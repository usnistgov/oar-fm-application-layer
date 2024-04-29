"""
This module provides a client class, NextcloudApi, designed to interact with the File Manager Generic Layer which is a REST API for Nextcloud.
"""
import requests
from requests.auth import HTTPBasicAuth
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class NextcloudApi:
    def __init__(self, config):
        self.is_prod = config['is_prod']
        if self.is_prod:
            self.base_url = config['nextcloud_api_prod_url'] + config['api_user'] + '/'
        else:
            self.base_url = config['nextcloud_api_dev_url']
        self.auth_user = config['api_user']
        self.auth_pass = config['api_pwd']

    def handle_request(self, method, url, **kwargs):
        """ Generic request handler. """
        full_url = f"{self.base_url}/{url}"
        try:
            auth = HTTPBasicAuth(self.auth_user, self.auth_pass)
            response = requests.request(method, full_url, auth=auth, verify=self.is_prod, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            err_msg = response.json().get('error', e)
            logging.error(f"HTTP Error {response.status_code} for {method} {full_url}: {err_msg}")
            raise Exception(f"HTTP Error {response.status_code}: {err_msg}")

    def test(self):
        """ Test the API connection. """
        return self.handle_request('GET', 'test')

    def headers(self):
        """ Fetch headers for debugging purposes. """
        return self.handle_request('GET', 'headers')

    def get_user_permissions(self, dir_name):
        """ Get all users permissions for a directory. """
        return self.handle_request('GET', f'files/userpermissions/{dir_name}')

    def set_user_permissions(self, user_name, perm_type, dir_name):
        """ Set user permissions for a directory. """
        return self.handle_request('POST', f'files/userpermissions/{user_name}/{perm_type}/{dir_name}')

    def delete_user_permissions(self, user_name, dir_name):
        """ Delete user permissions for a directory. """
        return self.handle_request('DELETE', f'files/userpermissions/{user_name}/{dir_name}')

    def scan_all_files(self):
        """ Trigger a scan for all files. """
        return self.handle_request('PUT', 'files/scan')

    def scan_user_files(self, user_name):
        """ Trigger a scan for all files from a user. """
        return self.handle_request('PUT', f'files/scan/{user_name}')

    def scan_directory_files(self, dir_path):
        """ Trigger a scan for all files inside a directory. """
        return self.handle_request('PUT', f'files/scan/directory/{dir_path}')

    def get_users(self):
        """ Get all users. """
        return self.handle_request('GET', 'files/users')

    def get_user(self, user_name):
        """ Get a single user. """
        return self.handle_request('GET', f'users/{user_name}')

    def create_user(self, user_name):
        """ Create a user. """
        return self.handle_request('POST', f'users/{user_name}')

    def disable_user(self, user_name):
        """ Disable a user. """
        return self.handle_request('PUT', f'users/{user_name}/disable')

    def enable_user(self, user_name):
        """ Enable a user. """
        return self.handle_request('PUT', f'users/{user_name}/enable')

