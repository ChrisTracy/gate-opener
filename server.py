import os
import threading
import time
import logging
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Table
import RPi.GPIO as GPIO
import jwt  # Import PyJWT

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
        ATcontents = table.all()

        global tokens
        global auths
        tokens = {}
        auths = []
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATconent in ATcontents:
            if "enabled" in ATconent['fields']:
                tokenVal = ATconent['fields']['token']
                userVal = ATconent['fields']['user']
                authVal = ATconent['fields']['auth']
                tokens.update({tokenVal: userVal})
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

# Verify token using JWT
@auth.verify_token
def verify_token(token):
    try:
        payload = jwt.decode(token, jwt_secret_key, algorithms=['HS256'])
        user = payload.get('user')
        if user in auths:
            return user
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
    return f"Hello, {current_user}. Your login to {friendly_name} was successful!"

# Register route - Issue tokens
@app.route('/api/v1/register', methods=["POST"])
def register():
    device = request.args.get('device')

    # Create a JWT token with user/device information
    import datetime
    expiration_date = datetime.datetime.utcnow() + datetime.timedelta(days=36500)
    token = jwt.encode({'user': device, 'exp': expiration_date}, jwt_secret_key, algorithm='HS256')

    # Store the token and user/device information in Airtable
    RawData = {"user": device, "auth": f"'user': {device}, 'exp': {expiration_date}"}
    table.create(RawData)
    logging.info('Registering new device: %s', device)

    return jsonify({"message": f"Your device ({device}) has been added to {friendly_name}. An admin must approve the request.", "token": token})
    
# Trigger route
@app.route('/api/v1/trigger', methods=["POST"])
@app.route('/gate/front/', methods=["POST"]) # Legacy route (will be deprecated)
@auth.login_required
def trigger():
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(.10)
    GPIO.output(pin, GPIO.LOW)
    current_user = auth.current_user()
    logging.info(f"{friendly_name} opened by {current_user}!")
    return f"{friendly_name} opened by {current_user}!"

# Refresh token route
@app.route('/api/v1/refreshtokens', methods=["POST"])
@auth.login_required
def refreshTokens():
    try:
        logging.info('Updating tokens. API call made by {}'.format(auth.current_user()))
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = os.environ['TOKEN_INTERVAL']
        Token_Interval = int(Token_Interval)

        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)
        ATcontents = table.all()

        global tokens
        tokens = {}

        if ATcontents is not None:
            for ATcontent in ATcontents:
                if "enabled" in ATcontent['fields']:
                    tokenVal = ATcontent['fields']['token']
                    userVal = ATcontent['fields']['user']
                    tokens.update({tokenVal: userVal})

        return "Tokens updated. Request made by {}!".format(auth.current_user())

    except:
        logging.exception("Could not reach Airtable!")
        return "Tokens could not be updated. Request made by {}!".format(auth.current_user())

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
