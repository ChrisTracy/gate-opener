import requests

def send_message(text,user,token):
    """Send a message"""
    payload = {"message": text, "user": user, "token": token }
    r = requests.post('https://api.pushover.net/1/messages.json', data=payload, headers={'User-Agent': 'Python'})
