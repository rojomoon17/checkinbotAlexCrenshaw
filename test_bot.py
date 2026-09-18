# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Scheduled Check-In Bot

"""Mock-based tests: no network access, no real Practice Hub calls. These
exercise edge cases that a handful of manual runs against the live API
during development wouldn't reliably hit - server pagination boundaries,
every HTTP error code (including malformed/non-JSON error bodies), and
per-post/per-attachment failure isolation. Run with:

    python -m unittest test_bot -v
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from practice_hub_client import PracticeHubClient, PracticeHubError, CheckInWindowClosed
from collect import run_collect
from checkin import run_checkin
import notify


def resp_with(status, json_body=None, json_raises=False, text="error text"):
    resp = mock.Mock()
    resp.ok = status < 400
    resp.status_code = status
    resp.text = text
    if json_raises:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = json_body or {}
    return resp


class TestPagination(unittest.TestCase):
    """PracticeHubClient.list_posts_by_author pages until a short page ends it."""

    def _client_with_pages(self, pages_by_offset):
        def fake_get(url, headers=None, params=None, **kwargs):
            resp = mock.Mock()
            resp.ok = True
            resp.status_code = 200
            resp.json.return_value = pages_by_offset.get(params["offset"], [])
            return resp

        client = PracticeHubClient("https://x", "t")
        return client, mock.patch("practice_hub_client.requests.get", side_effect=fake_get)

    def test_exact_multiple_of_limit(self):
        # 4 items at limit=2 means a 3rd request (offset=4) is needed to see
        # the empty page that signals "no more posts".
        pages = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}, {"id": 4}], 4: []}
        client, patch_ctx = self._client_with_pages(pages)
        with patch_ctx:
            result = client.list_posts_by_author(7, limit=2)
        self.assertEqual(len(result), 4)

    def test_uneven_last_page_stops_without_extra_request(self):
        pages = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}
        client, patch_ctx = self._client_with_pages(pages)
        with patch_ctx:
            result = client.list_posts_by_author(7, limit=2)
        self.assertEqual(len(result), 3)

    def test_zero_posts(self):
        client, patch_ctx = self._client_with_pages({0: []})
        with patch_ctx:
            result = client.list_posts_by_author(7, limit=2)
        self.assertEqual(result, [])

    def test_many_pages_preserve_order(self):
        all_items = [{"id": i} for i in range(250)]
        pages = {0: all_items[0:100], 100: all_items[100:200], 200: all_items[200:250]}
        client, patch_ctx = self._client_with_pages(pages)
        with patch_ctx:
            result = client.list_posts_by_author(7, limit=100)
        self.assertEqual([r["id"] for r in result], list(range(250)))


class TestCheckErrorHandling(unittest.TestCase):
    """_check() turns every HTTP error status into the right exception type."""

    def setUp(self):
        self.client = PracticeHubClient("https://x", "t")

    def test_status_codes_raise_expected_types(self):
        cases = [(401, PracticeHubError), (403, PracticeHubError), (404, PracticeHubError),
                  (422, PracticeHubError), (423, CheckInWindowClosed), (429, PracticeHubError),
                  (500, PracticeHubError)]
        for status, exc_type in cases:
            with self.subTest(status=status):
                with self.assertRaises(exc_type):
                    self.client._check(resp_with(status, {"detail": "boom"}))

    def test_423_is_a_practicehuberror_subclass(self):
        # So callers that only catch PracticeHubError still see it.
        self.assertTrue(issubclass(CheckInWindowClosed, PracticeHubError))

    def test_detail_as_list_of_dicts_422_style(self):
        with self.assertRaises(PracticeHubError) as ctx:
            self.client._check(resp_with(422, {"detail": [{"msg": "bad field"}, {"msg": "also bad"}]}))
        self.assertIn("bad field", str(ctx.exception))
        self.assertIn("also bad", str(ctx.exception))

    def test_non_json_error_body_does_not_crash(self):
        with self.assertRaises(PracticeHubError):
            self.client._check(resp_with(500, json_raises=True, text="<html>502</html>"))

    def test_ok_response_is_a_noop(self):
        self.client._check(resp_with(200))  # must not raise


class FakeClientForCollect:
    """Stands in for PracticeHubClient in run_collect() tests - no network."""

    def __init__(self, posts, fail_ids=None):
        self.posts = posts
        self.fail_ids = fail_ids or set()
        self.downloaded = []

    def list_posts_by_author(self, author_id, limit=100):
        return self.posts

    def download_attachment(self, attachment, dest_path):
        if attachment["id"] in self.fail_ids:
            raise PracticeHubError(f"simulated download failure for attachment {attachment['id']}")
        with open(dest_path, "wb") as f:
            f.write(b"fake-bytes")
        self.downloaded.append(attachment["id"])


class TestCollect(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.artifact_dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _collected(self):
        with open(os.path.join(self.artifact_dir, "collected.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_one_failed_attachment_does_not_drop_the_whole_post(self):
        posts = [{
            "id": 100, "title": "Multi-attachment post", "body": "three files incoming",
            "tags": ["demo"], "created_at": "t", "updated_at": "t",
            "attachments": [
                {"id": 1, "filename": "a.txt", "download_url": "/x/1"},
                {"id": 2, "filename": "b.txt", "download_url": "/x/2"},  # fails
                {"id": 3, "filename": "c.txt", "download_url": "/x/3"},
            ],
        }]
        client = FakeClientForCollect(posts, fail_ids={2})
        run_collect(client, 7, self.artifact_dir)

        data = self._collected()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Multi-attachment post")
        names = [a["filename"] for a in data[0]["attachments"]]
        self.assertIn("a.txt", names)
        self.assertIn("c.txt", names)
        self.assertNotIn("b.txt", names)

    def test_one_broken_post_does_not_affect_others(self):
        posts = [
            {"id": 1, "title": "Good 1", "body": "b1", "tags": [], "created_at": "t",
             "updated_at": "t", "attachments": []},
            {"id": 2, "title": "Broken", "body": "b2", "tags": [], "created_at": "t",
             "updated_at": "t", "attachments": [{"id": 5, "filename": "bad.txt", "download_url": "/x/5"}]},
            {"id": 3, "title": "Good 3", "body": "b3", "tags": [], "created_at": "t",
             "updated_at": "t", "attachments": []},
        ]
        client = FakeClientForCollect(posts, fail_ids={5})
        run_collect(client, 7, self.artifact_dir)
        self.assertEqual(sorted(p["id"] for p in self._collected()), [1, 2, 3])

    def test_rerun_does_not_redownload_existing_files(self):
        posts = [{"id": 1, "title": "t", "body": "b", "tags": [], "created_at": "t",
                  "updated_at": "t", "attachments": [{"id": 9, "filename": "f.txt", "download_url": "/x/9"}]}]
        client = FakeClientForCollect(posts)
        run_collect(client, 7, self.artifact_dir)
        self.assertEqual(client.downloaded, [9])
        client.downloaded = []
        run_collect(client, 7, self.artifact_dir)
        self.assertEqual(client.downloaded, [])

    def test_long_unicode_body_preserved_exactly(self):
        long_body = ("Paragraph.\n\n" * 50) + "emoji: \U0001F600 café"
        posts = [{"id": 1, "title": "Unicode", "body": long_body, "tags": [], "created_at": "t",
                  "updated_at": "t", "attachments": []}]
        run_collect(FakeClientForCollect(posts), 7, self.artifact_dir)
        self.assertEqual(self._collected()[0]["body"], long_body)

    def test_malicious_filename_cannot_escape_the_post_folder(self):
        posts = [{
            "id": 100, "title": "Malicious attachment", "body": "b", "tags": [],
            "created_at": "t", "updated_at": "t",
            "attachments": [
                {"id": 1, "filename": "../../../evil.txt", "download_url": "/x/1"},
                {"id": 2, "filename": "..\\..\\evil2.txt", "download_url": "/x/2"},
            ],
        }]
        run_collect(FakeClientForCollect(posts), 7, self.artifact_dir)

        # Nothing should land outside artifact/files/100/.
        parent_of_artifact = os.path.dirname(self.artifact_dir)
        self.assertFalse(os.path.exists(os.path.join(parent_of_artifact, "evil.txt")))
        self.assertFalse(os.path.exists(os.path.join(parent_of_artifact, "evil2.txt")))

        post_dir = os.path.join(self.artifact_dir, "files", "100")
        self.assertEqual(len(os.listdir(post_dir)), 2)


class FakeClientForCheckin:
    """Stands in for PracticeHubClient in run_checkin() tests - no network."""

    def __init__(self, posts, comments_by_post, raise_on_comment_get=None, window_open_for=None):
        self.posts = posts
        self.comments_by_post = comments_by_post
        self.raise_on_comment_get = raise_on_comment_get or set()
        self.window_open_for = window_open_for if window_open_for is not None else {p["id"] for p in posts}
        self.added_comments = []

    def list_posts_by_author(self, author_id, limit=100):
        return self.posts

    def list_comments(self, post_id):
        if post_id in self.raise_on_comment_get:
            raise PracticeHubError("network blip")
        return self.comments_by_post.get(post_id, [])

    def add_comment(self, post_id, body):
        if post_id not in self.window_open_for:
            raise CheckInWindowClosed("closed")
        self.added_comments.append((post_id, body))
        return {"id": 1, "body": body, "post_id": post_id, "author_id": 13}


class TestCheckin(unittest.TestCase):
    def test_only_literal_check_in_titles_are_targeted(self):
        posts = [
            {"id": 1, "title": "Regular update"},
            {"id": 2, "title": "Sept 18 check-in"},
            {"id": 3, "title": "check-in for Sept 19"},
            {"id": 4, "title": "CHECK-IN reminder"},
            {"id": 5, "title": "checkinformation about the course"},  # no hyphen
        ]
        client = FakeClientForCheckin(posts, {p["id"]: [] for p in posts})
        run_checkin(client, my_id=13, instructor_id=7)
        self.assertEqual(sorted(pid for pid, _ in client.added_comments), [2, 3, 4])

    def test_does_not_reply_twice(self):
        posts = [{"id": 1, "title": "Sept 18 check-in"}]
        comments = {1: [{"id": 10, "author_id": 13, "body": "already replied"}]}
        client = FakeClientForCheckin(posts, comments)
        summary = run_checkin(client, my_id=13, instructor_id=7)
        self.assertEqual(client.added_comments, [])
        self.assertEqual(summary["skipped_already_replied"], 1)

    def test_still_replies_when_only_others_have_commented(self):
        posts = [{"id": 1, "title": "Sept 18 check-in"}]
        comments = {1: [{"id": 10, "author_id": 999, "body": "someone else"}]}
        client = FakeClientForCheckin(posts, comments)
        summary = run_checkin(client, my_id=13, instructor_id=7)
        self.assertEqual(summary["replied"], 1)

    def test_window_closed_on_one_post_does_not_stop_the_rest(self):
        posts = [{"id": 1, "title": "Old check-in"}, {"id": 2, "title": "New check-in"}]
        comments = {1: [], 2: []}
        client = FakeClientForCheckin(posts, comments, window_open_for={2})
        summary = run_checkin(client, my_id=13, instructor_id=7)
        self.assertEqual(summary["skipped_window_closed"], 1)
        self.assertEqual(summary["replied"], 1)

    def test_comment_list_failure_on_one_post_does_not_stop_the_rest(self):
        posts = [{"id": 1, "title": "A check-in"}, {"id": 2, "title": "Another check-in"}]
        comments = {2: []}
        client = FakeClientForCheckin(posts, comments, raise_on_comment_get={1})
        summary = run_checkin(client, my_id=13, instructor_id=7)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["replied"], 1)

    def test_author_id_type_mismatch_does_not_cause_a_duplicate(self):
        # Defends against a server quirk where author_id might come back as
        # a string instead of an int.
        posts = [{"id": 1, "title": "Sept 18 check-in"}]
        comments = {1: [{"id": 10, "author_id": "13", "body": "already replied"}]}
        client = FakeClientForCheckin(posts, comments)
        run_checkin(client, my_id=13, instructor_id=7)
        self.assertEqual(client.added_comments, [])

    def test_notify_called_only_on_success_or_real_failure(self):
        calls = []
        notify_fn = lambda message: calls.append(message)

        # Success.
        client = FakeClientForCheckin([{"id": 1, "title": "Sept 18 check-in"}], {1: []})
        run_checkin(client, my_id=13, instructor_id=7, notify=notify_fn)
        self.assertEqual(len(calls), 1)

        # Real failure.
        calls.clear()
        client = FakeClientForCheckin([{"id": 2, "title": "Another check-in"}], {2: []},
                                       raise_on_comment_get={2})
        run_checkin(client, my_id=13, instructor_id=7, notify=notify_fn)
        self.assertEqual(len(calls), 1)

        # Already replied - must stay silent.
        calls.clear()
        client = FakeClientForCheckin([{"id": 3, "title": "Sept 17 check-in"}],
                                       {3: [{"id": 99, "author_id": 13, "body": "x"}]})
        run_checkin(client, my_id=13, instructor_id=7, notify=notify_fn)
        self.assertEqual(calls, [])

        # Window closed on an old check-in - must stay silent.
        calls.clear()
        client = FakeClientForCheckin([{"id": 4, "title": "Old check-in"}], {4: []},
                                       window_open_for=set())
        run_checkin(client, my_id=13, instructor_id=7, notify=notify_fn)
        self.assertEqual(calls, [])

    def test_omitting_notify_defaults_to_a_safe_noop(self):
        client = FakeClientForCheckin([{"id": 1, "title": "Sept 18 check-in"}], {1: []})
        run_checkin(client, my_id=13, instructor_id=7)  # must not raise


class TestNotify(unittest.TestCase):
    def test_noops_without_a_topic(self):
        notify.send(None, "message")
        notify.send("", "message")  # must not raise or attempt an HTTP call


class TestMainValidation(unittest.TestCase):
    def test_non_numeric_instructor_id_is_a_clean_error_not_a_raw_traceback(self):
        with mock.patch.dict(os.environ, {
            "PRACTICE_API_URL": "https://x",
            "PRACTICE_API_TOKEN": "t",
            "INSTRUCTOR_ID": "not-a-number",
        }, clear=False):
            import main
            with self.assertRaises(SystemExit):
                main.main()


if __name__ == "__main__":
    unittest.main()
