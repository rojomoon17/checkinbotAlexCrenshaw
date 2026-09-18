# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Scheduled Check-In Bot

import requests


class PracticeHubError(Exception):
    """A non-success response came back from the Practice Hub API."""


class CheckInWindowClosed(PracticeHubError):
    """The API returned 423: this check-in isn't open for replies right now."""


class PracticeHubClient:
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def _check(self, resp):
        if resp.ok:
            return
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, list):
            detail = "; ".join(
                d.get("msg", str(d)) if isinstance(d, dict) else str(d) for d in detail
            )
        status = resp.status_code
        if status == 401:
            raise PracticeHubError(
                "401 Unauthorized: your API token is missing or invalid. "
                "Re-check the PRACTICE_API_TOKEN value and try again.")
        if status == 403:
            raise PracticeHubError(
                "403 Forbidden: you don't have permission to do that.")
        if status == 404:
            raise PracticeHubError("404 Not Found: no resource exists with that id.")
        if status == 423:
            raise CheckInWindowClosed(
                "423 Locked: this check-in's reply window isn't open right now.")
        if status == 422:
            raise PracticeHubError(
                f"422 Invalid data: {detail or 'check the fields you sent.'}")
        raise PracticeHubError(
            f"{status} error from the API: {detail or resp.text[:200]}")

    def me(self):
        resp = requests.get(f"{self.base}/api/v1/me", headers=self.headers, timeout=30)
        self._check(resp)
        return resp.json()

    def list_posts_by_author(self, author_id, limit=100):
        posts = []
        offset = 0
        while True:
            resp = requests.get(
                f"{self.base}/api/v1/posts",
                headers=self.headers,
                params={"author": author_id, "limit": limit, "offset": offset},
                timeout=30,
            )
            self._check(resp)
            page = resp.json()
            posts.extend(page)
            if len(page) < limit:
                break
            offset += limit
        return posts

    def list_comments(self, post_id):
        resp = requests.get(
            f"{self.base}/api/v1/posts/{post_id}/comments", headers=self.headers, timeout=30)
        self._check(resp)
        return resp.json()

    def add_comment(self, post_id, body):
        resp = requests.post(
            f"{self.base}/api/v1/posts/{post_id}/comments",
            headers=self.headers, json={"body": body}, timeout=30)
        self._check(resp)
        return resp.json()

    def download_attachment(self, attachment, dest_path):
        url = attachment["download_url"]
        if not url.startswith("http"):
            url = f"{self.base}{url}"
        resp = requests.get(url, headers=self.headers, stream=True, timeout=30)
        self._check(resp)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
