import threading
import datetime
import time
import logging
import jwt
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from waitress import serve
import sqlite3
import os
import RPi.GPIO as GPIO
from modules.send_html_email import send_dynamic_email
import modules.helper as helper
import notify.pushover as pushover
import config

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

# Create SQLite database if not exists
db_file = 'user_tokens.db'
if not os.path.exists(db_file):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''CREATE TABLE user_tokens
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, auth TEXT, enabled BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

# Function to get tokens from SQLite
def get_tokens(thread=False):
    try:
        logging.info('Getting tokens from SQLite')
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute('SELECT user, auth FROM user_tokens')
        auths = c.fetchall()
        conn.close()
        
        if thread == True:
            threading.Timer(config.token_interval, get_tokens, args=(True,)).start()
        else:
            return ('Token refresh completed')

    except Exception as e:
        logging.exception("Could not fetch tokens from SQLite: %s", str(e))

# Run get tokens on the specified interval
threading.Thread(target=get_tokens, args=(True,)).start()

# Setup GPIO
logging.info('Setting up GPIO on pin %s', config.pin)
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(config.pin, GPIO.OUT)
GPIO.output(config.pin, GPIO.LOW)

# Initialize Flask
app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

# Verify token using JWT
@auth.verify_token
def verify_token(token):
    try:
        payload = jwt.decode(token, config.jwt_secret_key, algorithms=['HS256'])
        numAuth = payload.get('rand')
        rand_value_str = str(numAuth)
        device_str = payload.get('device')
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute('SELECT auth FROM user_tokens WHERE user = ?', (device_str,))
        user_auth = c.fetchone()
        conn.close()
        if user_auth and rand_value_str in user_auth[0]:
            global current_user_name
            global isAdmin
            current_user_name = device_str  # Assuming the device name is the user name
            isAdmin = False  # No admin control in this version
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
    return f"Hello {current_user_name}. You logged in to {config.friendly_name} successfully!"

# Register route - Issue tokens
@app.route('/api/v1/user/register', methods=["POST"])
def register():
    device = request.args.get('device')
    psk = request.args.get('psk')
    
    if psk == config.register_user_psk:
        if device is not None:
            # Create a JWT token with user/device information
            expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=config.jwt_expiration_days)
            random_16_char_string = helper.generate_random_string(16)
            invite_string = helper.generate_random_string(30)
            host = config.proxy_url
            token = jwt.encode({'device': device, 'rand': random_16_char_string}, config.jwt_secret_key, algorithm='HS256')
    
            # Store the token and user/device information in SQLite
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute('INSERT INTO user_tokens (user, auth) VALUES (?, ?)', (device, f'{{"device":"{device}", "rand":"{random_16_char_string}"}}'))
            conn.commit()
            conn.close()
            logging.info('Registering new device: %s', device)
    
            #send email
            if config.sender_email and config.receiver_email and config.smtp_password and config.proxy_url:
                # Define a dictionary of variables and their values
                variables = {
                    'friendly_name': config.friendly_name,
                    'device_name': device,
                    'host': config.proxy_url,
                    'invite_str': invite_string,
                    'psk': config.approval_psk,
                }
                
                subject = f"New Device Request for {config.friendly_name}"
                
                # Call the send_dynamic_email function
                send_dynamic_email(config.sender_email, config.receiver_email, config.smtp_server, config.smtp_port, config.smtp_username, config.smtp_password, subject, config.html_file_path, variables)
    
            return jsonify({"message": f"Your device ({device}) has been added to {config.friendly_name}. An admin must approve the request.", "host": host, "token": token})
        else:
            return jsonify({"message": "Missing the device parameter"})
    else:
        logging.exception('PSK did not match on register route. Provided PSK: %s', psk)
        return jsonify({"message": "Invalid PSK. Access denied."}), 401

# Trigger route
@app.route('/api/v1/trigger', methods=["POST"])
@auth.login_required
def trigger():
    GPIO.output(config.pin, GPIO.HIGH)
    time.sleep(.10)
    GPIO.output(config.pin, GPIO.LOW)

    logging.info("%s opened by %s", config.friendly_name, current_user_name)
    if config.pushover_user and config.pushover_token:
        logging.info("Sending pushover notification for trigger route")
        triggerMessage = f"{config.friendly_name} opened by {current_user_name}"
        pushover.send_message(text=triggerMessage,user=config.pushover_user,token=config.pushover_token)

    return f"{config.friendly_name} opened by {current_user_name}"

# Refresh token route
@app.route('/api/v1/refreshtokens', methods=["POST"])
@auth.login_required
def refresh_tokens():
    return ("Token refresh completed")

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)