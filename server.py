import os
import threading
import datetime
import time
import logging
import json
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Table
import RPi.GPIO as GPIO
import random
import jwt

# Set GPIO pin and friendly name
friendly_name = os.environ['FRIENDLY_NAME']
pin = int(os.environ['GPIO_PIN'])

# Set JWT secret key (keep this secret) and client token expiration
jwt_secret_key = os.environ['JWT_SECRET_KEY']
JWT_EXPIRATION_DAYS = int(os.environ.get('JWT_EXPIRATION_DAYS', 1))

# Function to pull tokens
def get_tokens():
    try:
        logging.info('Getting tokens from AirTable')
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = int(os.environ['TOKEN_INTERVAL'])

        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)

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

        threading.Timer(Token_Interval, get_tokens).start()

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

# Run get tokens
get_tokens()

# Setup GPIO
logging.info('Setting up GPIO on pin %s', pin)
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
            current_user_name = get_user_by_device(ATcontents, device_str)
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
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=JWT_EXPIRATION_DAYS)
        num = random.random()
        token = jwt.encode({'device': device, 'rand': num}, jwt_secret_key, algorithm='HS256')

        # Store the token and user/device information in Airtable
        RawData = {"user": device, "auth": f"\"device\":\"{device}\", \"rand\":{num}"}
        table.create(RawData)
        logging.info('Registering new device: %s', device)

        return jsonify({"message": f"Your device ({device}) has been added to {friendly_name}. An admin must approve the request.", "token": token})
    else:
        return jsonify({"message": "Missing the device parameter"})

# Trigger route
@app.route('/api/v1/trigger', methods=["POST"])
@app.route('/gate/front/', methods=["POST"])  # Legacy route (will be deprecated)
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
    try:
        logging.info('Token refresh requested by %s', current_user_name)
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = int(os.environ['TOKEN_INTERVAL'])

        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)

        global ATcontents
        ATcontents = table.all()

        global auths
        auths = []

        global user_auth_dict
        user_auth_dict = {}

        if ATcontents is not None:
            for ATcontent in ATcontents:
                if "enabled" in ATcontent['fields']:
                    userVal = ATcontent['fields']['user']
                    authVal = ATcontent['fields']['auth']
                    user_auth_dict[userVal] = authVal
                    auths.append(authVal)
        logging.info('Tokens were manually refreshed by %s', current_user_name)
        return f"Tokens were manually refreshed by {current_user_name}"

    except Exception as e:
        logging.exception("Could not reach Airtable: %s", str(e))

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
