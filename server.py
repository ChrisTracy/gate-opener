from flask import Flask, request
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Table
import RPi.GPIO as GPIO
import os
import threading
import time
import logging

pin = 16

logging.basicConfig(filename='app.log',
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

def getTokens():
    os.environ['AT_API_KEY'] = ''
    os.environ['Base_ID'] = ''
    os.environ['Table_Name'] = 'users'

    at_api_key = os.environ['AT_API_KEY']
    AT_BaseID  = os.environ['Base_ID']
    AT_TableName = os.environ['Table_Name']

    global table
    table = Table(api_key=at_api_key, base_id=AT_BaseID, table_name=AT_TableName)
    ATcontents = table.all()

    global tokens
    tokens = {}

    for ATconent in ATcontents:
        if "enabled" in ATconent['fields']:
            tokenVal = ATconent['fields']['token']
            userVal = ATconent['fields']['user']
            tokens.update({tokenVal: userVal})

    threading.Timer(21600, getTokens).start()

getTokens()

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin,GPIO.OUT)
GPIO.output(pin,GPIO.HIGH)

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

@auth.verify_token
def verify_token(token):
    if token in tokens:
        return tokens[token]

@app.route('/welcome')
@auth.login_required
def index():
    return "Hello, {}!".format(auth.current_user())

def register():
    device = request.args.get('device')
    key = request.args.get('key')

    RawData = {"user": device, "token":key}
    table.create(RawData)

    return "Device key has been added. An admin must approve the request!"


@app.route('/gate/front/', methods=["POST"])
@auth.login_required
def open():
    GPIO.output(pin,GPIO.LOW)
    time.sleep(.10)
    GPIO.output(pin,GPIO.HIGH)
    logging.info('Gate opened by {}'.format(auth.current_user()))
    return "Gate opened by {}!".format(auth.current_user())

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)

