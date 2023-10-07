import os
import threading
import time
import logging
from flask import Flask, request
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Table
import RPi.GPIO as GPIO

#set gpio pin
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
    if token in tokens:
        return tokens[token]

#welcome route
@app.route('/api/v1/hello')
@auth.login_required
def index():
    return "Hello, {}!".format(auth.current_user())

#register route
@app.route('/api/v1/register', methods=["POST"])

#register function
def register():
    device = request.args.get('device')
    key = request.args.get('key')

    RawData = {"user": device, "token":key}
    table.create(RawData)
    logging.info('Registering new device: %s', device)
    return "Device key has been added. An admin must approve the request!"

#open route
@app.route('/api/v1/trigger', methods=["POST"])
@auth.login_required

#open function
def open():
    GPIO.output(pin,GPIO.HIGH)
    time.sleep(.10)
    GPIO.output(pin,GPIO.LOW)
    logging.info('Gate opened by {}'.format(auth.current_user()))
    return "Gate opened by {}!".format(auth.current_user())

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
    except:
        logging.exception("Could not reach Airtable!")

    if ATcontents is not None:
        for ATconent in ATcontents:
            if "enabled" in ATconent['fields']:
                tokenVal = ATconent['fields']['token']
                userVal = ATconent['fields']['user']
                tokens.update({tokenVal: userVal})

#start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
