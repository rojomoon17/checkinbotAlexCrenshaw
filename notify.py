# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Scheduled Check-In Bot

import requests


def send(topic, message, title=None):
    if not topic:
        return
    headers = {}
    if title:
        headers["Title"] = title
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"),
                       headers=headers, timeout=10)
    except requests.exceptions.RequestException as err:
        print(f"  ! failed to send push notification: {err}")
