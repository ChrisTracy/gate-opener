import os
import threading
import datetime
import time
import logging
import json
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Api
import RPi.GPIO as GPIO
import random
import string
import jwt

# Set GPIO pin and friendly name
friendly_name = os.environ['FRIENDLY_NAME']
pin = int(os.environ['GPIO_PIN'])

# Set JWT secret key (keep this secret) and client token expiration
jwt_secret_key = os.environ['JWT_SECRET_KEY']
JWT_EXPIRATION_DAYS = int(os.environ.get('JWT_EXPIRATION_DAYS', 365))

# Function to pull tokens
def get_tokens(thread=False):
    try:
        logging.info('Getting tokens from AirTable')
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = int(os.environ['TOKEN_INTERVAL'])

        global api
        global table
        api = Api(at_api_key)
        table = api.table(base_id=AT_BaseID, table_name=AT_TableName)

        global ATcontents
        ATcontents = table.all()

        global auths
        auths = []

        global user_auth_dict
        user_auth_dict = {}

        global current_user_name
        current_user_name = None

        if ATcontents is not None:
            for ATcontent in ATcontents:
                if "enabled" in ATcontent['fields']:
                    userVal = ATcontent['fields']['user']
                    authVal = ATcontent['fields']['auth']
                    user_auth_dict[userVal] = authVal
                    auths.append(authVal)
        
        if thread == True:
            threading.Timer(Token_Interval, get_tokens).start()
        else:
            return ('Token refresh completed')

    except Exception as e:
        logging.exception("Could not reach Airtable: %s", str(e))

# Setup console logging and file logging
log_format = "%(asctime)s [%(levelname)s] %(message)s"
log_file_debug = "debug.log"
log_file_info = "info.log"

logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(log_file_debug),
        logging.FileHandler(log_file_info),
        logging.StreamHandler()
    ]
)

# Run get tokens on the specified interval
threading.Thread(target=get_tokens, args=(True,)).start()

# Setup GPIO
logging.info('Setting up GPIO on pin %s', pin)
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT)
GPIO.output(pin, GPIO.LOW)

# Initialize Flask
app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

# Helper function to get user by their device
def get_user_by_device(ATcontents, desired_device_name):
    for user_data in ATcontents:
        if "auth" in user_data['fields']:
            auth_val = user_data['fields']['auth']
            try:
                auth_data = json.loads("{" + auth_val + "}")
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
                auth_data = json.loads("{" + auth_val + "}")
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
            if invite_val:
                return user_data
    return None

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

# Verify token using JWT
@auth.verify_token
def verify_token(token):
    try:
        payload = jwt.decode(token, jwt_secret_key, algorithms=['HS256'])
        numAuth = payload.get('rand')
        rand_value_str = str(numAuth)
        device_str = payload.get('device')
        is_rand_in_auth = any(rand_value_str in element for element in auths)
        if is_rand_in_auth:
            global current_user_name
            global isAdmin
            current_user_name = get_user_by_device(ATcontents, device_str)
            isAdmin = get_admin_by_device(ATcontents, device_str) 
            logging.info("Token found! Auth Successful for %s", current_user_name)
            return True
    except jwt.ExpiredSignatureError:
        logging.error('Token has expired')
    except jwt.InvalidTokenError:
        logging.error('Invalid token')

    return None

# Welcome route
@app.route('/api/v1/hello')
@auth.login_required
def index():
    current_user = auth.current_user()
    return f"Hello {current_user_name}. You logged in to {friendly_name} successfully!"

# Register route - Issue tokens
@app.route('/api/v1/register', methods=["POST"])
def register():
    device = request.args.get('device')

    if device is not None:
        # Create a JWT token with user/device information
        expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=JWT_EXPIRATION_DAYS)
        random_16_char_string = generate_random_string(16)
        invite_string = generate_random_string(30)
        token = jwt.encode({'device': device, 'rand': random_16_char_string}, jwt_secret_key, algorithm='HS256')

        # Store the token and user/device information in Airtable
        RawData = {"user": device, "auth": f"\"device\":\"{device}\", \"rand\":{random_16_char_string}", "invite": invite_string}
        table.create(RawData)
        logging.info('Registering new device: %s', device)

        return jsonify({"message": f"Your device ({device}) has been added to {friendly_name}. An admin must approve the request.", "token": token})
    else:
        return jsonify({"message": "Missing the device parameter"})

# Trigger route
@app.route('/api/v1/trigger', methods=["POST"])
@auth.login_required
def trigger():
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(.10)
    GPIO.output(pin, GPIO.LOW)

    logging.info("%s opened by %s", friendly_name, current_user_name)
    return f"{friendly_name} opened by {current_user_name}"

# Refresh token route
@app.route('/api/v1/refreshtokens', methods=["POST"])
@auth.login_required
def refresh_tokens():
    if isAdmin == True:
        logging.info("Token refresh requested by %s", current_user_name)
        try:
            get_tokens()
            return ("Token refresh completed")
        except:
            logging.info("Token refresh could not be completed")
            return ("Token refresh could not be completed. Review the logs.")
    else:
        logging.info("%s does not have admin permissions to call refresh token route.", current_user_name)
        return f"Access denied. You do not have access to this route!"

@app.route('/api/v1/enable', methods=['GET'])
def enable():
    invite = request.args.get('invite')
    if invite:
        try:
            get_tokens()
            logging.info("Attempting to Enable user with invite %s", invite)
            user = get_user_by_invite(ATcontents=ATcontents, invite_str=invite)
            tableItemID = user['id']
            enabled = None
            enabled = user['fields'].get('enabled')
            logging.info(enabled)
            if tableItemID:
                if enabled != True:
                    table.update(tableItemID, {"enabled": True})
                    logging.info("User enabled with invite: %s", invite)
                    get_tokens()
                    return f"User was enabled. Invite: {invite}"
                else:
                    return f"No action taken. User is already enabled. Invite: {invite}"
            else:
                return f"Could not find table item for invite: {invite}"
        except Exception as e: 
            logging.error(f"Not able to enable device. Invite: {invite}. Error: {e}")
            return f"Not able to enable device. Invite: {invite}"
    else:
        logging.info("Invite not found in the URL")
        return 'Invite not found in the URL'

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
