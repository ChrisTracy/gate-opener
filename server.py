import os
import datetime
import time
import logging
import jwt
import sqlite3
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from waitress import serve
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

# Initialize and setup database
def init_db():
    db_directory = '/db'
    db_path = f'{db_directory}/users.db'
    
    # Ensure the directory exists
    if not os.path.exists(db_directory):
        os.makedirs(db_directory)

    # Connect to the SQLite database (creates if not exists)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the 'users' table if it does not already exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            auth TEXT,
            enabled BOOLEAN DEFAULT FALSE,
            admin BOOLEAN DEFAULT FALSE,
            invite TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized (if it was not already).")

init_db()

# Setup GPIO
logging.info('Setting up GPIO on pin %s', config.pin)
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(config.pin, GPIO.OUT)
GPIO.output(config.pin, GPIO.LOW)

# Initialize Flask
app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

# Verify token using JWT and check in the database directly
@auth.verify_token
def verify_token(token):
    try:
        payload = jwt.decode(token, config.jwt_secret_key, algorithms=['HS256'])
        num_auth = str(payload.get('rand'))
        invite_str = payload.get('device')
        logging.debug("JWT decoded successfully. Payload: %s", payload)

        with sqlite3.connect('/db/users.db') as conn:
            cursor = conn.cursor()
            sql_query = "SELECT user, admin FROM users WHERE invite = ? AND auth LIKE ? AND enabled = TRUE"
            cursor.execute(sql_query, (invite_str, f'%{num_auth}%'))
            user_info = cursor.fetchone()
            logging.debug("SQL Query executed. Result: %s", user_info)

            if user_info:
                global current_user_name, isAdmin
                current_user_name, isAdmin = user_info
                logging.info("Token verified! Auth successful for %s", current_user_name)
                return True
    except jwt.ExpiredSignatureError:
        logging.error('Token has expired')
        return False
    except jwt.InvalidTokenError:
        logging.error('Invalid token')
        return False
    except Exception as e:
        logging.error("Unexpected error during token verification: %s", str(e))
        return False


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
            expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=config.jwt_expiration_days)
            random_16_char_string = helper.generate_random_string(16)
            invite_string = helper.generate_random_string(30)
            host = config.proxy_url
            token = jwt.encode({'device': device, 'rand': random_16_char_string}, config.jwt_secret_key, algorithm='HS256')

            conn = sqlite3.connect('/db/users.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (user, auth, invite) VALUES (?, ?, ?)", (device, f'{{"device":"{device}", "rand":"{random_16_char_string}"}}', invite_string))
            conn.commit()
            conn.close()

            logging.info('Registering new device: %s', device)

            if config.sender_email and config.receiver_email and config.smtp_password and config.proxy_url:
                variables = {
                    'friendly_name': config.friendly_name,
                    'device_name': device,
                    'host': config.proxy_url,
                    'invite_str': invite_string,
                    'psk': config.approval_psk,
                }
                subject = f"New Device Request for {config.friendly_name}"
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
        triggerMessage = f"{config.friendly_name} opened by {current_user_name}"
        pushover.send_message(text=triggerMessage, user=config.pushover_user, token=config.pushover_token)
    return f"{config.friendly_name} opened by {current_user_name}"

# Enable route
@app.route('/api/v1/user/enable', methods=['GET'])
def enable():
    invite = request.args.get('invite')
    psk = request.args.get('psk')

    if psk == config.approval_psk: 
        if invite:
            with sqlite3.connect('/db/users.db') as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET enabled = TRUE WHERE invite = ? AND enabled = FALSE", (invite,))
                if cursor.rowcount > 0:
                    conn.commit()
                    logging.info("User enabled with invite: %s", invite)
                    return f"User was enabled. Invite: {invite}"
                else:
                    return f"No action taken. User may already be enabled or invite not found. Invite: {invite}"
        else:
            logging.info("Invite parameter missing in the request")
            return 'Invite parameter missing in the request'
    else:
        logging.error('PSK did not match on enable route. Provided PSK: %s', psk)
        return jsonify({"message": "Invalid PSK. Access denied."}), 401

# Reject route
@app.route('/api/v1/user/reject', methods=['GET'])
def reject():
    invite = request.args.get('invite')
    psk = request.args.get('psk')

    if psk == config.approval_psk: 
        if invite:
            with sqlite3.connect('/db/users.db') as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE invite = ?", (invite,))
                if cursor.rowcount > 0:
                    conn.commit()
                    logging.info("User with invite %s has been deleted", invite)
                    return f"User with invite {invite} has been deleted"
                else:
                    return f"Could not find user for invite: {invite}"
        else:
            logging.info("Invite parameter missing in the request")
            return 'Invite parameter missing in the request'
    else:
        logging.error('PSK did not match on reject route. Provided PSK: %s', psk)
        return jsonify({"message": "Invalid PSK. Access denied."}), 401

# Start server
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5151)