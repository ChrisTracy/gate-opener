import json
import random
import string

# Helper function to get user by their device
def get_user_by_device(ATcontents, desired_device_name):
    for user_data in ATcontents:
        if "auth" in user_data['fields']:
            auth_val = user_data['fields']['auth']
            try:
                auth_data = json.loads(auth_val)
                dev = auth_data.get('device')
                if auth_data.get('device') == desired_device_name:
                    user_name = user_data['fields'].get('user')
                    if user_name:
                        return user_name
            except json.JSONDecodeError:
                pass
    return None

# Helper function to get admin by their device
def get_admin_by_device(ATcontents, desired_device_name):
    for user_data in ATcontents:
        if "auth" in user_data['fields']:
            auth_val = user_data['fields']['auth']
            try:
                auth_data = json.loads(auth_val)
                if auth_data.get('device') == desired_device_name:
                    admin = user_data['fields'].get('admin')
                    if admin:
                        return admin
            except json.JSONDecodeError:
                pass
    return None

# Helper function to get user by their invite ID
def get_user_by_invite(ATcontents, invite_str):
    for user_data in ATcontents:
        if "invite" in user_data['fields']:
            invite_val = user_data['fields']['invite']
            if invite_val == invite_str:
                return user_data
    return None

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string