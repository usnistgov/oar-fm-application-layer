"""
Config variables set up
"""

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    NEXTCLOUD_API_PROD_URL = os.environ.get("NEXTCLOUD_API_PROD_URL")
    NEXTCLOUD_API_DEV_URL = os.environ.get("NEXTCLOUD_API_DEV_URL")
    API_USER = os.environ.get("API_USER")
    API_PWD = os.environ.get("API_PWD")
    PROD = False
    NEXTCLOUD_ROOT_DIR_PATH = os.environ.get("NEXTCLOUD_ROOT_DIR_PATH")
    WEBDAV_PROD_URL = os.environ.get("WEBDAV_PROD_URL")
    WEBDAV_DEV_URL = os.environ.get("WEBDAV_DEV_URL")
    CLIENT_CERT_PATH = os.environ.get("CLIENT_CERT_PATH")
    CLIENT_KEY_PATH = os.environ.get("CLIENT_KEY_PATH")
    SERVER_CA_PATH = os.environ.get("SERVER_CA_PATH")
    NEXTCLOUD_ADMIN_USER = os.environ.get("NEXTCLOUD_ADMIN_USER")
