import os
import threading
import time
import logging
from flask import Flask, request
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Table
import RPi.GPIO as GPIO
from cryptography.fernet import Fernet

#set gpio pin and friendly name
friendly_name = os.environ['FRIENDLY_NAME']
pin = os.environ['GPIO_PIN']
pin = int(pin)

#setup console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

#function to pull tokens
def getTokens():
    try:
        logging.info('Getting tokens from AirTable')
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID  = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = os.environ['TOKEN_INTERVAL']
        Token_Interval = int(Token_Interval)
    
        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)
        ATcontents = table.all()
    
        global tokens
        tokens = {}
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATconent in ATcontents:
            if "enabled" in ATconent['fields']:
                tokenVal = ATconent['fields']['token']
                userVal = ATconent['fields']['user']
                tokens.update({tokenVal: userVal})

    threading.Timer(Token_Interval, getTokens).start()

#run get tokens
getTokens()

#setup gpio
logging.info('Setting up GPIO on pin %s', pin)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin,GPIO.OUT)
GPIO.output(pin,GPIO.LOW)

#init flask
app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

#verify token
@auth.verify_token
def verify_token(token):
    if token:
        try:
            # Decode (decrypt) the token
            decoded_token = base64.b64decode(token).decode()
            if decoded_token in tokens:
                return tokens[decoded_token]
        except Exception as e:
            logging.error('Token decryption failed: %s', str(e))
    return None

#welcome route
@app.route('/api/v1/hello')
@auth.login_required
def index():
    current_user = auth.current_user()
    return f"Hello, {current_user}. Your login to {friendly_name} was succesful!"

#register route
@app.route('/api/v1/register', methods=["POST"])

#register function
def register():
   def register():
    device = request.args.get('device')
    key = request.args.get('key')

    # Encrypt the device token
    encrypted_token = base64.b64encode(key.encode()).decode()

    # Store the encrypted token and user/device information in Airtable
    RawData = {"user": device, "token": encrypted_token}
    table.create(RawData)
    logging.info('Registering new device: %s', device)
    return f"Your device ({device}) has been added to {friendly_name}. An admin must approve the request!"

#trigger route
@app.route('/api/v1/trigger', methods=["POST"])
@app.route('/gate/front/', methods=["POST"]) #legacy. Will be deprecated
@auth.login_required

#trigger function
def trigger():
    GPIO.output(pin,GPIO.HIGH)
    time.sleep(.10)
    GPIO.output(pin,GPIO.LOW)
    current_user = auth.current_user()
    logging.info(f"{friendly_name} opened by {current_user}!")
    return f"{friendly_name} opened by {current_user}!"

#refresh token route
@app.route('/api/v1/refreshtokens', methods=["POST"])
@auth.login_required

#refresh tokens function
def refreshTokens():
    try:
        logging.info('Updating tokens. API call made by {}'.format(auth.current_user()))
        at_api_key = os.environ['AT_API_KEY']
        AT_BaseID  = os.environ['BASE_ID']
        AT_TableName = os.environ['TABLE_NAME']
        Token_Interval = os.environ['TOKEN_INTERVAL']
        Token_Interval = int(Token_Interval)
    
        global table
        table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)
        ATcontents = table.all()
    
        global tokens
        tokens = {}
        
        if ATcontents is not None:
            for ATconent in ATcontents:
                if "enabled" in ATconent['fields']:
                    tokenVal = ATconent['fields']['token']
                    userVal = ATconent['fields']['user']
                    tokens.update({tokenVal: userVal})

        return "Tokens updated. Request made by {}!".format(auth.current_user())

    except:
        logging.exception("Could not reach Airtable!")
        return "Tokens could not be updated. Request made by {}!".format(auth.current_user())

#start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
