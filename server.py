import os
import threading
import datetime
import time
import logging
import json
import jwt
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from waitress import serve
from pyairtable import Api
import RPi.GPIO as GPIO
from modules.send_html_email import send_dynamic_email
import modules.helper as helper
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

# Function to pull tokens
def get_tokens(thread=False):
    try:
        logging.info('Getting tokens from AirTable')
        global api
        global table
        api = Api(config.at_api_key)
        table = api.table(base_id=config.at_baseid, table_name=config.at_tablename)

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
            threading.Timer(config.token_interval, get_tokens, args=(True,)).start()
        else:
            return ('Token refresh completed')

    except Exception as e:
        logging.exception("Could not reach Airtable: %s", str(e))

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
        is_rand_in_auth = any(rand_value_str in element for element in auths)
        if is_rand_in_auth:
            global current_user_name
            global isAdmin
            current_user_name = helper.get_user_by_device(ATcontents, device_str)
            isAdmin = helper.get_admin_by_device(ATcontents, device_str)
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
            token = jwt.encode({'device': device, 'rand': random_16_char_string}, config.jwt_secret_key, algorithm='HS256')
    
            # Store the token and user/device information in Airtable
            RawData = {"user": device, "auth": f'{{"device":"{device}", "rand":"{random_16_char_string}"}}', "invite": invite_string}
            table.create(RawData)
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
    
            return jsonify({"message": f"Your device ({device}) has been added to {config.friendly_name}. An admin must approve the request.", "token": token})
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
    return f"{config.friendly_name} opened by {current_user_name}"

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

@app.route('/api/v1/user/enable', methods=['GET'])
def enable():
    invite = request.args.get('invite')
    psk = request.args.get('psk')

    if psk == config.approval_psk: 
        if invite:
            try:
                get_tokens()
                logging.info("Attempting to Enable user with invite %s", invite)
                user = helper.get_user_by_invite(ATcontents=ATcontents, invite_str=invite)
                tableItemID = user['id']
                enabled = user['fields'].get('enabled')
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
                return f"Invite code not found. Ensure ivite code is correct. Invite: {invite}"
        else:
            logging.info("Invite not found in the URL")
            return 'Invite not found in the URL'
    else:
       logging.exception('PSK did not match on enable route. Provided PSK: %s', psk)
       return jsonify({"message": "Invalid PSK. Access denied."}), 401


@app.route('/api/v1/user/reject', methods=['GET'])
def reject():
    invite = request.args.get('invite')
    psk = request.args.get('psk')

    if psk == config.approval_psk: 
        if invite:
            try:
                get_tokens()
                logging.info("Attempting to reject user with invite %s", invite)
                user = helper.get_user_by_invite(ATcontents=ATcontents, invite_str=invite)
                tableItemID = user['id']
                if tableItemID:
                    table.delete(tableItemID)
                    get_tokens()
                    return f"User was deleted from table. Invite: {invite}"
                else:
                    return f"Could not find table item for invite: {invite}"
            except Exception as e: 
                logging.error(f"Not able to delete device. Invite: {invite}. Error: {e}")
                return f"Invite code not found. Ensure ivite code is correct. Invite: {invite}"
        else:
            logging.info("Invite not found in the URL")
            return 'Invite not found in the URL'
    else:
       logging.exception('PSK did not match on enable route. Provided PSK: %s', psk)
       return jsonify({"message": "Invalid PSK. Access denied."}), 401

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)
