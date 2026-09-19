# checkinbotAlexCrenshaw

INF601 - Advanced Programming in Python
Scheduled Check-In Bot - Alex Crenshaw

## What this project does

A GitHub Actions workflow runs `main.py` on a cron schedule. Each run talks
to the class **Practice Hub** API (`https://practice.fhsucyber.com`) as the
instructor's user id and does two things:

1. **Collects everything the instructor posts** (`collect.py`) - every post's
   title, full body, tags, and timestamps, plus every attached file
   downloaded (not just noted), into `artifact/collected.json` and
   `artifact/files/`.
2. **Replies to each daily check-in on time** (`checkin.py`) - finds posts
   whose title contains "check-in" and posts a comment while that post's
   reply window is open. A `423` response (window not open) is handled as a
   normal, expected outcome, not an error. Before replying, it checks the
   post's existing comments for one already authored by this bot's own user
   id, so re-running the same day never posts a duplicate.

Optionally, it also sends a phone push notification (via
[ntfy.sh](https://ntfy.sh)) when a check-in reply actually succeeds or hits
a real failure - it stays silent for the two routine outcomes (already
replied today, or a `423` on an old/past check-in), so you're not paged for
things that need no attention.

`main.py` wires both together and is what the workflow actually runs.
`practice_hub_client.py` is this project's Practice Hub API client (built on
the same pattern as Mini Project 1's `client.py`), extended with pagination,
comments, and attachment downloads.

## Requirements

- Python 3.8 or newer
- [`requests`](https://pypi.org/project/requests/) (listed in `requirements.txt`)

```bash
pip install -r requirements.txt
```

## Configuration

The bot reads three values from the environment - never hardcode or commit
any of them:

| Name | Kind | Value |
| --- | --- | --- |
| `PRACTICE_API_TOKEN` | Secret | your Practice Hub API token |
| `PRACTICE_API_URL` | Secret | `https://practice.fhsucyber.com` |
| `INSTRUCTOR_ID` | Variable | the instructor's Practice Hub user id |
| `NTFY_TOPIC` | Secret (optional) | a private [ntfy.sh](https://ntfy.sh) topic name for push notifications |

**On GitHub** (required for the scheduled workflow): repo -> Settings ->
Secrets and variables -> Actions -> add all four there (the first two and
`NTFY_TOPIC` as Secrets, `INSTRUCTOR_ID` as a Variable). The workflow reads
them as:

```yaml
env:
  PRACTICE_API_TOKEN: ${{ secrets.PRACTICE_API_TOKEN }}
  PRACTICE_API_URL: ${{ secrets.PRACTICE_API_URL }}
  INSTRUCTOR_ID: ${{ vars.INSTRUCTOR_ID }}
  NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
```

**Locally**, set the same values as environment variables in your shell
before running (PowerShell shown, same as Mini Project 1):

```powershell
$env:PRACTICE_API_TOKEN = "your-token-here"
$env:PRACTICE_API_URL = "https://practice.fhsucyber.com"
$env:INSTRUCTOR_ID = "7"
$env:NTFY_TOPIC = "your-private-topic-name"   # optional
```

If `PRACTICE_API_TOKEN`, `PRACTICE_API_URL`, or `INSTRUCTOR_ID` are missing,
`main.py` exits immediately with a message instead of making requests.
`NTFY_TOPIC` is optional - without it, notifications are simply skipped and
everything else behaves the same.

### Setting up push notifications (optional)

1. Install the [ntfy app](https://ntfy.sh/) on your phone (iOS/Android).
2. Pick a private topic name (any hard-to-guess string - anyone who knows
   it can read your notifications, since ntfy.sh topics aren't secret by
   nature, only obscure).
3. In the app, subscribe to that topic.
4. Add the same string as the `NTFY_TOPIC` repo secret.

You'll then get a push notification whenever the bot successfully replies
to a check-in, or hits a real failure trying to - and nothing otherwise.

## Running it

```bash
python main.py
```

This runs Task 1 then Task 2 and prints a short summary of each, e.g.:

```text
running as 'Alex Crenshaw' (id 13)
Task 1: collecting instructor posts...
  {'posts_collected': 16, 'files_downloaded': 0}
Task 2: replying to open check-ins...
  window closed for check-in 36: 'Check-in for Sept 17'
  ...
  {'checkins_found': 12, 'replied': 0, 'skipped_already_replied': 1, 'skipped_window_closed': 11, 'failed': 0}
```

It's safe to run repeatedly: already-downloaded files aren't re-fetched, and
already-answered check-ins are skipped rather than re-replied to.

## The scheduled workflow

`.github/workflows/checkin-bot.yml` runs on:

- `schedule` - cron `0 12,17,22 * * *` (UTC), which is **07:00 / 12:00 /
  17:00 Central** (CDT, UTC-5 - in effect for all of Weeks 4-6 this term).
  Three runs a day give margin: if one run fails or is delayed, the next one
  the same day still catches an open check-in, and the duplicate-reply check
  makes the extra runs harmless. All three times are far from the
  04:00-06:00 UTC window called out in the assignment (00:00-01:00 Central),
  where a delayed run risks sliding into the next day and missing a
  check-in entirely.
- `workflow_dispatch` - so it can also be triggered by hand from the Actions
  tab.

`permissions: contents: write` is set at the top level of the workflow file
because the default `GITHUB_TOKEN` can read the repo but not push to it; the
last step needs to commit `artifact/` back.

## Tests

`test_bot.py` is a `unittest` suite (no extra dependency - it only uses
`unittest.mock` from the standard library) that exercises edge cases a
handful of manual runs against the live API wouldn't reliably hit:
pagination boundaries, every HTTP error status the client can get back
(including a malformed/non-JSON error body), a crafted attachment filename
(`../../evil.txt`) that must not be able to write outside its post's
folder, one failed attachment/post not taking the rest of a batch down
with it, the duplicate-reply guard (including an `author_id` type
mismatch), the closed-window (`423`) path, and exactly which outcomes do
and don't trigger a push notification.

Writing it this way - fake, in-memory stand-ins for `PracticeHubClient`
instead of hitting the real API - is what caught 4 real bugs during
development that a live run against real data hadn't (a live run only
ever exercises the data that happens to exist that day, not the edge
cases): a failed attachment used to silently drop its whole post record,
attachment filenames weren't sanitized against path traversal, the
duplicate-reply check would have missed a string/int type mismatch, and a
bad `INSTRUCTOR_ID` crashed with a raw traceback instead of a clean error.
All four are fixed in the current code and now have a regression test.

Run it with:

```bash
python -m unittest test_bot -v
```

## Error handling

`practice_hub_client.py`'s `_check()` helper replaces
`response.raise_for_status()` and turns API errors into a readable
`PracticeHubError` (or the more specific `CheckInWindowClosed` for a `423`).
Every HTTP call also sets a 30-second timeout, so a hung connection fails
fast instead of stalling a run for the workflow's full job timeout.
`collect.py` and `checkin.py` each wrap their per-post work in `try`/`except`
so one bad post or a closed check-in window doesn't stop the rest of the
batch. `main.py` has a top-level `try`/`except` that catches
`PracticeHubError` (API errors) and `requests.exceptions.RequestException`
(network/timeout errors) and prints one line instead of a raw traceback for
those specific cases - a genuinely unexpected bug elsewhere would still
surface as a full traceback and a non-zero exit, which is intentional so it
isn't silently swallowed.

## AI Usage

### What Claude Code did

- Read the Practice Hub OpenAPI spec to find the pagination params,
  attachment/comment endpoints, and check-in window behavior.
- Wrote `practice_hub_client.py`, `collect.py`, `checkin.py`, `main.py`,
  `notify.py`, and `test_bot.py`.
- Wrote the GitHub Actions workflow (`checkin-bot.yml`).
- Diagnosed a local-machine-only SSL issue (Avast's HTTPS-scanning proxy)
  and built a temporary CA bundle to test against the live API.
- Ran the bot against the live Practice Hub API repeatedly during
  development, including after every later change.
- Wrote a mock-based test harness and used it to find and fix 4 bugs:
  a failed attachment dropping its whole post record, unsanitized
  attachment filenames allowing path traversal, a type-fragile
  duplicate-reply check, and a raw crash on a bad `INSTRUCTOR_ID`.
  Cleaned up and committed as `test_bot.py`.
- Added missing request timeouts in `practice_hub_client.py`.
- Verified real scheduled runs on GitHub's own runner via its REST API,
  including one run GitHub itself delayed by ~2.5 hours.
- Wrote this README.
