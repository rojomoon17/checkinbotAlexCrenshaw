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

I used Claude Code (Anthropic's CLI) to build this project, working from
Mini Project 1's `client.py` as the starting pattern.

- **Researched the real API shape** before writing anything, by fetching
  `practice.fhsucyber.com/openapi.json` directly, since Mini Project 1 only
  used the plain CRUD endpoints and never needed pagination, attachments,
  or comments. That's where the `author`/`limit`/`offset` pagination
  params, the embedded `attachments[]` on each post, the comments
  endpoints, and the fact that the server enforces the check-in window
  itself (so a `423` can just be handled, never parsed from a title) all
  came from.
- **Wrote every `.py` file**: `practice_hub_client.py` (extending Mini
  Project 1's client with `me()`, paginated `list_posts_by_author()`,
  comments, and streaming attachment downloads), `collect.py` (Task 1),
  `checkin.py` (Task 2), `main.py` (entry point), `notify.py` (optional
  ntfy.sh push notifications), and `test_bot.py` (the mock-based test
  suite).
- **Wrote the GitHub Actions workflow** (`checkin-bot.yml`) - the cron
  schedule, `workflow_dispatch`, `permissions: contents: write`, and the
  commit-back step.
- **Diagnosed and fixed a local-machine-only SSL failure** during
  development (Avast's HTTPS-scanning proxy injects a root certificate
  that Python's `certifi` bundle doesn't trust, even though `curl` trusts
  it via the Windows certificate store) and built a temporary local CA
  bundle to test against the live API with - this only ever affected
  testing on this one machine and isn't part of the deployed bot or its
  dependencies.
- **Ran the bot against the live Practice Hub API repeatedly** throughout
  development and after every change: verified Task 1's collected
  bodies/attachments byte-for-byte against fresh re-downloads, verified
  Task 2's duplicate-reply guard by running it twice in a row, and
  re-verified the full bot end-to-end after every later change (timeouts,
  notifications) to confirm identical output and no unintended `artifact/`
  diff.
- **Wrote a mock-based test harness** (no live API calls) specifically to
  stress-test edge cases a handful of manual runs against real data
  wouldn't reliably hit - pagination boundaries, every HTTP error status
  including malformed/non-JSON bodies, and per-post/per-attachment failure
  isolation. This found 4 real bugs, which Claude Code then fixed: a
  failed attachment download used to silently drop its whole post record
  (title/body/tags/other attachments, not just the one file) instead of
  just skipping that attachment; attachment filenames were used
  unsanitized, so a crafted filename containing `../` could write outside
  `artifact/files/<post_id>/`; the duplicate-reply check compared
  `author_id` with `==`, which would miss a match (and cause a real
  duplicate reply) if the API ever returned it as a string instead of an
  int; and a non-numeric `INSTRUCTOR_ID` crashed with a raw `ValueError`
  traceback instead of the same clean error message used for other
  misconfiguration. All four fixes were re-verified against the live API
  afterward to confirm no behavior changed for real data, then that mock
  harness was cleaned up and committed as `test_bot.py`.
- **Found and fixed a missing-timeout gap**: none of `practice_hub_client.py`'s
  HTTP calls set a `timeout`, so a hung connection could stall a run for
  the workflow's full job timeout instead of failing fast. Added
  `timeout=30` to all five calls and re-verified against the live API.
- **Verified real scheduled runs on GitHub's own runner**, not just local
  runs: checked run/job status via GitHub's REST API after each real
  cron firing, including one that GitHub itself delayed by roughly 2.5
  hours from its scheduled time (a documented GitHub Actions behavior for
  top-of-the-hour schedules) - confirmed the duplicate-reply guard still
  correctly prevented a second reply on that delayed run.
- **Wrote this README**, including documenting the secrets/variables
  table, the cron schedule's reasoning, the optional push-notification
  setup, and this AI Usage section.
