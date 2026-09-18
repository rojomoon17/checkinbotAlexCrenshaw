# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Scheduled Check-In Bot

import json
import os


def run_collect(client, instructor_id, artifact_dir):
    posts = client.list_posts_by_author(instructor_id)

    records = []
    files_downloaded = 0
    for post in posts:
        try:
            record = {
                "id": post["id"],
                "title": post["title"],
                "body": post["body"],
                "tags": post.get("tags", []),
                "created_at": post.get("created_at"),
                "updated_at": post.get("updated_at"),
                "attachments": [],
            }
            post_dir = os.path.join(artifact_dir, "files", str(post["id"]))
            for attachment in post.get("attachments", []):
                os.makedirs(post_dir, exist_ok=True)
                filename = f"{attachment['id']}_{attachment['filename']}"
                dest_path = os.path.join(post_dir, filename)
                if not os.path.exists(dest_path):
                    client.download_attachment(attachment, dest_path)
                    files_downloaded += 1
                local_path = os.path.relpath(dest_path, artifact_dir).replace(os.sep, "/")
                record["attachments"].append({
                    "id": attachment["id"],
                    "filename": attachment["filename"],
                    "local_path": local_path,
                })
            records.append(record)
        except Exception as err:
            print(f"  ! failed to collect post {post.get('id')}: {err}")

    os.makedirs(artifact_dir, exist_ok=True)
    collected_path = os.path.join(artifact_dir, "collected.json")
    with open(collected_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return {"posts_collected": len(records), "files_downloaded": files_downloaded}
