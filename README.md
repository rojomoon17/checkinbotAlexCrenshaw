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

## Error handling

`practice_hub_client.py`'s `_check()` helper replaces
`response.raise_for_status()` and turns API errors into a readable
`PracticeHubError` (or the more specific `CheckInWindowClosed` for a `423`).
`collect.py` and `checkin.py` each wrap their per-post work in `try`/`except`
so one bad post or a closed check-in window doesn't stop the rest of the
batch, and `main.py` has a top-level `try`/`except` so an unexpected error
prints one line instead of a raw traceback.
