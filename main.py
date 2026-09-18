# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Scheduled Check-In Bot

import os

import requests

from practice_hub_client import PracticeHubClient, PracticeHubError
from collect import run_collect
from checkin import run_checkin

ARTIFACT_DIR = "artifact"


def main():
    base_url = os.environ.get("PRACTICE_API_URL")
    token = os.environ.get("PRACTICE_API_TOKEN")
    instructor_id = os.environ.get("INSTRUCTOR_ID")

    if not base_url or not token or not instructor_id:
        raise SystemExit(
            "PRACTICE_API_URL, PRACTICE_API_TOKEN, and INSTRUCTOR_ID must all be "
            "set - see the README for how to configure them.")

    try:
        instructor_id = int(instructor_id)
    except ValueError:
        raise SystemExit(f"INSTRUCTOR_ID must be an integer, got {instructor_id!r}.")

    client = PracticeHubClient(base_url, token)

    try:
        me = client.me()
        print(f"running as {me['name']!r} (id {me['id']})")

        print("Task 1: collecting instructor posts...")
        collect_summary = run_collect(client, instructor_id, ARTIFACT_DIR)
        print(f"  {collect_summary}")

        print("Task 2: replying to open check-ins...")
        checkin_summary = run_checkin(client, me["id"], instructor_id)
        print(f"  {checkin_summary}")
    except PracticeHubError as err:
        raise SystemExit(f"Request failed - {err}")
    except requests.exceptions.RequestException as err:
        raise SystemExit(f"Could not reach the practice hub - {err}")


if __name__ == "__main__":
    main()
