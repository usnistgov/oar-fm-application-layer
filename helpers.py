"""
helpers methods
"""
import hashlib
import xml.etree.ElementTree as ET


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


def parse_nextcloud_scan_xml(scan_result):
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

    return files


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
