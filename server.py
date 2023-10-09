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
authenticated_user_name = None

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
        ATcontents = table.all()

        global auths
        auths = []

        # Create a dictionary to store the mapping of rand to user
        global rand_to_user_mapping
        rand_to_user_mapping = {}
        
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATcontent in ATcontents:
            if "enabled" in ATcontent['fields']:
                userVal = ATcontent['fields']['user']
                authVal = ATcontent['fields']['auth']
                auths.append(authVal)

                if "auth" in ATcontent['fields']:
                    authVal = ATcontent['fields']['auth']
                    
                    # Check if the authVal string contains the expected format
                    if ": " in authVal:
                        auth_parts = authVal.split(', ')
                        rand_value_str = auth_parts[0].split(': ')[1].strip()  # Extract rand value as string
                        user_str = auth_parts[1].split(': ')[1].strip()  # Extract user value as string
                        
                        try:
                            rand_value = float(rand_value_str)  # Convert rand value to float
                            rand_to_user_mapping[rand_value] = user_str  # Build the mapping
                        except ValueError:
                            logging.error(f"Invalid rand value: {rand_value_str}")
                    else:
                        logging.error(f"Invalid authVal format: {authVal}")
                        
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

# Verify token using JWT
@auth.verify_token
def verify_token(token):
    try:
        payload = jwt.decode(token, jwt_secret_key, algorithms=['HS256'])
        logging.info(f"{payload} is attempting to authenticate!")
        numAuth = payload.get('rand')
        rand_value_str = str(numAuth)
        is_rand_in_auth = any(rand_value_str in element for element in auths)
        if is_rand_in_auth:
            logging.info(f"Token found! Auth Successful.")
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
    return f"Your login to {friendly_name} was successful!"

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
        logging.info('Registering new device: %s', device)
    
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
    
    rand_value = float(current_user.split(': ')[1])
    authenticated_user_name = rand_to_user_mapping.get(rand_value)
    
    logging.info(f"{friendly_name} opened by {authenticated_user_name}!")
    return (f"{friendly_name} opened")
# Refresh token route
@app.route('/api/v1/refreshtokens', methods=["POST"])
@auth.login_required
def refreshTokens():
    try:
        logging.info('Getting tokens from AirTable')
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = os.environ['TOKEN_INTERVAL']
        Token_Interval = int(Token_Interval)

        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)
        ATcontents = table.all()

        global auths
        auths = []
        
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATcontent in ATcontents:
            if "enabled" in ATcontent['fields']:
                userVal = ATcontent['fields']['user']
                authVal = ATcontent['fields']['auth']
                auths.append(authVal)            

        return "Tokens updated. Request made by {}!".format(auth.current_user())

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
