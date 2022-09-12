from tokenize import Token
from flask import Flask
from flask_httpauth import HTTPTokenAuth
from waitress import serve
import RPi.GPIO as GPIO
import os
import re
import time

pin = os.environ['PIN']

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin,GPIO.OUT)
GPIO.output(pin,GPIO.HIGH)

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')


list = os.environ
tokens = {}

for user in list:
    if "user" in user:
        Unum = re.findall(r'\d+', user)
        for token in list:
            if "token" in token:
                Tnum = re.findall(r'\d+', token)
                if Unum == Tnum:
                    tokenVal = os.environ[token]
                    userVal = os.environ[user]
                    tokens.update({tokenVal: userVal})

@auth.verify_token
def verify_token(token):
    if token in tokens:
        return tokens[token]

@app.route('/welcome')
@auth.login_required
def index():
    return "Hello, {}!".format(auth.current_user())

@app.route('/gate/front/', methods=["POST"])
@auth.login_required
def open():
    GPIO.output(pin,GPIO.LOW)
    time.sleep(.10)
    GPIO.output(pin,GPIO.HIGH)

    return "Gate opened by {}!".format(auth.current_user())

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
