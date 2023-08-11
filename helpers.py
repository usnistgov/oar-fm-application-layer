"""
helpers methods
"""


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