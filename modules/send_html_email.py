import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re

def send_dynamic_email(sender_email, receiver_email, smtp_server, smtp_port, smtp_username, smtp_password, subject, html_file_path, variables):
    # Read the HTML content from the specified file
    with open(html_file_path, "r") as file:
        html_content = file.read()

    # REGEX to match variables within curly braces, e.g., {variable_name}
    pattern = r'\{([^}]+)\}'

    # Define a function to replace the matched variables
    def replace_variable(match):
        variable_name = match.group(1)
        return variables.get(variable_name, match.group(0))

    # Replace variables within the HTML content
    modified_html = re.sub(pattern, replace_variable, html_content)

    # Create the MIME object
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    # Attach the HTML content
    msg.attach(MIMEText(modified_html, "html"))

    # Start the SMTP server and send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return ("Email sent successfully")
    except Exception as e:
        return (f"Email could not be sent. Error: {e}")
