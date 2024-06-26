"""
helpers methods
"""
import hashlib
import os
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from urllib.parse import unquote


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
    filtered_files = []
    for file in files:
        file_path = file['path']
        if not file_path.endswith((user_dir, user_dir + '/')):
            filtered_files.append(file)

    return filtered_files


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
    correct_path = get_correct_path(file_path)
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    with open(correct_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def get_correct_path(path):
    decoded_path = unquote(path)
    if os.path.exists(decoded_path):
        return decoded_path
    else:
        return path


def extract_exception_message(xml_list):
    # Combine the list of strings into a single XML string
    xml_data = ''.join(xml_list)

    # Parse the XML
    root = ET.fromstring(xml_data)

    # Extract the exception message
    namespace = {'d': 'DAV:', 's': 'http://sabredav.org/ns'}
    exception = root.find('.//s:exception', namespace)
    message = root.find('.//s:message', namespace)

    if exception is not None and message is not None:
        return {'error': exception.text, 'message': message.text}

    return None


def extract_status_code(xml_list):
    # Join the list into a single string
    xml_data = ''.join(xml_list)

    # Parse the XML data
    root = ET.fromstring(xml_data)

    # Find the status code element and get its text
    status_code_element = root.find('.//statuscode')
    if status_code_element is not None:
        status_code = int(status_code_element.text)
    else:
        status_code = None

    return status_code


def calculate_size(contents):
    total_size = 0
    for item in contents:
        if item['resource_type'] == 'file':
            total_size += int(item['size'])
    return str(total_size)
