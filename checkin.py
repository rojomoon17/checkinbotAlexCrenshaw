# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Scheduled Check-In Bot

from datetime import datetime, timezone

from practice_hub_client import CheckInWindowClosed


def run_checkin(client, my_id, instructor_id, notify=None):
    if notify is None:
        notify = lambda message: None

    posts = client.list_posts_by_author(instructor_id)
    checkins = [p for p in posts if "check-in" in p["title"].lower()]

    replied = 0
    skipped_already_replied = 0
    skipped_window_closed = 0
    failed = 0

    for post in checkins:
        post_id = post["id"]
        try:
            comments = client.list_comments(post_id)
            if any(str(c.get("author_id")) == str(my_id) for c in comments):
                skipped_already_replied += 1
                continue

            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            client.add_comment(post_id, f"Alex Crenshaw checking in - {timestamp}.")
            replied += 1
            print(f"  replied to check-in {post_id}: {post['title']!r}")
            notify(f"Replied to check-in: {post['title']!r}")
        except CheckInWindowClosed:
            skipped_window_closed += 1
            print(f"  window closed for check-in {post_id}: {post['title']!r}")
        except Exception as err:
            failed += 1
            print(f"  ! failed to reply to check-in {post_id}: {err}")
            notify(f"FAILED to reply to check-in {post_id} ({post['title']!r}): {err}")

    return {
        "checkins_found": len(checkins),
        "replied": replied,
        "skipped_already_replied": skipped_already_replied,
        "skipped_window_closed": skipped_window_closed,
        "failed": failed,
    }
