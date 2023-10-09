import os
import threading
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
pin = os.environ['GPIO_PIN']
pin = int(pin)

# Set JWT secret key (keep this secret)
jwt_secret_key = os.environ['JWT_SECRET_KEY']

# Setup console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

# Function to pull tokens
def getTokens():
    try:
        logging.info('Getting tokens from AirTable')
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = os.environ['TOKEN_INTERVAL']
        Token_Interval = int(Token_Interval)

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
    
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATcontent in ATcontents:
            if "enabled" in ATcontent['fields']:
                userVal = ATcontent['fields']['user']
                authVal = ATcontent['fields']['auth']
                user_auth_dict[userVal] = authVal
                auths.append(authVal)
                        
    threading.Timer(Token_Interval, getTokens).start()

# Run get tokens
getTokens()

# Setup GPIO
logging.info('Setting up GPIO on pin %s', pin)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT)
GPIO.output(pin, GPIO.LOW)

# Initialize Flask
app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

#get user by their device
def get_user_by_device(ATcontents, desired_device_name):
    # Iterate through 'ATcontents'
    for user_data in ATcontents:
        if "auth" in user_data['fields']:
            auth_val = user_data['fields']['auth']
            try:
                # Parse the 'auth' value as JSON
                auth_data = json.loads("{" + auth_val + "}")

                # Check if the 'device' field in auth_data matches the desired device name
                if auth_data.get('device') == desired_device_name:
                    # If it matches, return the 'user' field as a string
                    user_name = user_data['fields'].get('user')
                    if user_name:
                        return user_name
            except json.JSONDecodeError:
                # Handle invalid JSON data in 'auth' field if necessary
                pass

    # If no matching user is found, return None
    return None

# Verify token using JWT
@auth.verify_token
@auth.verify_token
def verify_token(token):
    try:
        payload = jwt.decode(token, jwt_secret_key, algorithms=['HS256'])
        logging.info(f"Token payload: {payload}")
        numAuth = payload.get('rand')
        rand_value_str = str(numAuth)
        device_str = payload.get('device')
        logging.info(f"Device: {device_str}")
        is_rand_in_auth = any(rand_value_str in element for element in auths)
        if is_rand_in_auth:
            global current_user_name
            current_user_name = get_user_by_device(ATcontents, device_str)
            logging.info(f"Token found! Auth Successful for {current_user_name}")
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
    return f"Hello {current_user_name}. You login to {friendly_name} was successful!"

# Register route - Issue tokens
@app.route('/api/v1/register', methods=["POST"])
def register():
    device = request.args.get('device')

    if device is not None:
        # Create a JWT token with user/device information
        import datetime
        expiration_date = datetime.datetime.utcnow() + datetime.timedelta(days=36500)
        num = random.random()
        token = jwt.encode({'device':device, 'rand':num}, jwt_secret_key, algorithm='HS256')
    
        # Store the token and user/device information in Airtable
        RawData = {"user": device, "auth": f"\"device\":\"{device}\", \"rand\":{num}"}
        table.create(RawData)
        logging.info(f'Registering new device: {device}')
    
        return jsonify({"message": f"Your device ({device}) has been added to {friendly_name}. An admin must approve the request.", "token": token})
    else:
        return jsonify({"message": "Missing the device parameter"})
    
# Trigger route
@app.route('/api/v1/trigger', methods=["POST"])
@app.route('/gate/front/', methods=["POST"]) # Legacy route (will be deprecated)
@auth.login_required
def trigger():
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(.10)
    GPIO.output(pin, GPIO.LOW)
    
    logging.info(f"{friendly_name} opened by {current_user_name}")
    return (f"{friendly_name} opened by {current_user_name}")
# Refresh token route
@app.route('/api/v1/refreshtokens', methods=["POST"])
@auth.login_required
def refreshTokens():
    try:
        logging.info(f'Manually refreshing tokens from AirTable. API call made by {current_user_name}')
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = os.environ['TOKEN_INTERVAL']
        Token_Interval = int(Token_Interval)

        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)

        global ATcontents
        ATcontents = table.all()

        global auths
        auths = []

        global user_auth_dict
        user_auth_dict = {}
    
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATcontent in ATcontents:
            if "enabled" in ATcontent['fields']:
                userVal = ATcontent['fields']['user']
                authVal = ATcontent['fields']['auth']
                user_auth_dict[userVal] = authVal
                auths.append(authVal)

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
