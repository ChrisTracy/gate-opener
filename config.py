import os

#server envs
friendly_name = os.environ['FRIENDLY_NAME']

#GPIO envs
pin = int(os.environ['GPIO_PIN'])

# JWT envs
jwt_secret_key = os.environ['JWT_SECRET_KEY']
jwt_expiration_days = int(os.environ.get('JWT_EXPIRATION_DAYS', 365))

# SMTP envs
proxy_url = (os.environ.get('PROXY_URL', None))
sender_email = (os.environ.get('SENDER_EMAIL', None))
receiver_email = (os.environ.get('RECEIVER_EMAIL', None))
smtp_server = (os.environ.get('SMTP_SERVER', "smtp.gmail.com"))
smtp_port = int(os.environ.get('SMTP_PORT', 587))
smtp_username = (os.environ.get('SMTP_USERNAME', sender_email))
smtp_password = (os.environ.get('SMTP_PASSWORD', None))
html_file_path = (os.environ.get('HTML_FILE_PATH', "html/new-user-email.html"))  # Path to the HTML file

#PSK envs
register_user_psk = os.environ['REGISTER_PSK']
approval_psk = os.environ['APPROVAL_PSK']

#AirTable envs
at_api_key = os.environ['AT_API_KEY']
at_baseid = os.environ['BASE_ID']
at_tablename = os.environ['TABLE_NAME']
token_interval = int(os.environ['TOKEN_INTERVAL'])

#Pushover envs
pushover_user = (os.environ.get('PUSHOVER_USER', None))
pushover_token = (os.environ.get('PUSHOVER_TOKEN', None))
