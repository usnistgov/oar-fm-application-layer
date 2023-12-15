"""
helpers methods
"""
import hashlib
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from pathlib import Path
from app.utils import files


def get_permissions_string(permission_number):
    if permission_number == 0:
        return "No permissions (No access to the file or folder)"
    elif 1 <= permission_number <= 3:
        return "Read"
    elif 4 <= permission_number <= 7:
        return "Write"
    elif 8 <= permission_number <= 15:
        return "Delete"
    elif 16 <= permission_number <= 29:
        return "Share"
    elif permission_number == 30 or permission_number == 31:
        return "All"
    else:
        return "Invalid permissions"


def get_permissions_number(permission_string):
    if permission_string == "No permissions (No access to the file or folder)":
        return 0
    elif permission_string == "Read":
        return 3
    elif permission_string == "Write":
        return 7
    elif permission_string == "Delete":
        return 15
    elif permission_string == "Share":
        return 29
    elif permission_string == "All":
        return 31
    else:
        return "Invalid permissions"


def extract_failure_msgs(response):
    failure_msgs = ''

    if isinstance(response, list):
        elements = ''.join(response).split('<message>')[1:]
    else:
        elements = response.content.decode().split('<message>')[1:]

    for element in elements:
        element = element.split('<')[0].replace("\\", "")
        if element.lower() != 'ok' and element not in failure_msgs:
            if failure_msgs != '':
                failure_msgs += ', \n'
            failure_msgs += element

    return failure_msgs


def extract_permissions(response):
    if isinstance(response, list):
        element = ''.join(response)
    else:
        element = response.content.decode()

    if '<permissions>' not in element:
        return 'No permissions'

    element = element.split('<permissions>')[1:][0]
    permissions = int(element.split('<')[0].replace("\\", ""))

    return permissions


def parse_nextcloud_scan_xml(user_dir, scan_result):
    # namespaces
    ns = {
        'd': 'DAV:',
        'oc': 'http://owncloud.org/ns',
        'nc': 'http://nextcloud.org/ns'
    }

    # Convert the list to a single string
    xml_string = ''.join(scan_result)

    root = ET.fromstring(xml_string)
    files = []

    for response in root.findall('d:response', ns):
        file_info = {}

        # Extract href which is the path of the file/directory
        href = response.find('d:href', ns)
        if href is not None:
            file_info['path'] = href.text

        # Extract properties
        for propstat in response.findall('d:propstat', ns):
            prop = propstat.find('d:prop', ns)
            if prop is not None:
                for child in prop:
                    # Remove namespace from tag for clean representation
                    tag = child.tag.split('}')[-1]
                    file_info[tag] = child.text

        files.append(file_info)

    # remove the dict associated to the user dir
    ud_parts = user_dir.parts
    for file in files:
        file_path = Path(file['path'])
        fp_parts = file_path.parts
        if fp_parts[-len(ud_parts):] == ud_parts:
            filtered_files = [f for f in files if f.get('path') != file_path]
            return filtered_files

    return files


def determine_resource_type(resource: dict) -> str:
    """
    Determines whether the resource is a folder or a file based on its path.
    Assumes that folder paths end with a slash and file paths do not.
    """
    path = resource['path']
    if path.endswith('/'):
        return 'folder'
    else:
        return 'file'


def find_last_modified(nextcloud_resource):
    """
    Find the date a file has last been modified in a user record space
    based on its path
    """
    if isinstance(nextcloud_resource, list):
        # Response is from get_directory
        xml_str = ''.join(nextcloud_resource)
    elif isinstance(nextcloud_resource, dict) and 'metadata' in nextcloud_resource:
        # Response is from get_file
        xml_str = nextcloud_resource['metadata']
    else:
        raise ValueError("Invalid nextcloud resource format")

    nextcloud_resource = ''.join(nextcloud_resource)

    # Parse the XML
    root = ET.fromstring(xml_str)

    # Find the getLastModified element
    namespaces = {'d': 'DAV:'}
    last_modified_element = root.find('.//d:getlastmodified', namespaces)

    if last_modified_element is None:
        raise ValueError("Last modified date not found in the nextcloud resource")

    last_modified_value = last_modified_element.text

    # Convert to ISO format
    datetime_obj = parsedate_to_datetime(last_modified_value)
    iso_formatted_time = datetime_obj.isoformat()

    return iso_formatted_time


def calculate_checksum(file_path: str, algorithm: str = "sha256") -> str:
    """Calculate the checksum of a file.

    Args:
        file_path (str): Path to the file.
        algorithm (str): Algorithm to use for checksum. Currently only supports "sha256".

    Returns:
        str: The computed checksum.

    Raises:
        ValueError: If an unsupported algorithm is provided.
    """
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b""):
            hasher.update(chunk)

    return hasher.hexdigest()
