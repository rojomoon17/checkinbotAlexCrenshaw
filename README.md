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

**On GitHub** (required for the scheduled workflow): repo -> Settings ->
Secrets and variables -> Actions -> add all three there (the first two as
Secrets, `INSTRUCTOR_ID` as a Variable). The workflow reads them as:

```yaml
env:
  PRACTICE_API_TOKEN: ${{ secrets.PRACTICE_API_TOKEN }}
  PRACTICE_API_URL: ${{ secrets.PRACTICE_API_URL }}
  INSTRUCTOR_ID: ${{ vars.INSTRUCTOR_ID }}
```

**Locally**, set the same three as environment variables in your shell
before running (PowerShell shown, same as Mini Project 1):

```powershell
$env:PRACTICE_API_TOKEN = "your-token-here"
$env:PRACTICE_API_URL = "https://practice.fhsucyber.com"
$env:INSTRUCTOR_ID = "7"
```

If any of the three are missing, `main.py` exits immediately with a message
instead of making requests.

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

## AI Usage

I used Claude Code to build this project. Everything below is accurate to
what actually happened in that session, and I can explain every line,
including the workflow YAML.

**What Claude Code did:**

- Read the OpenAPI spec at `practice.fhsucyber.com/openapi.json` to work out
  the real pagination params (`author`/`limit`/`offset`), the embedded
  `attachments[]` on each post, the comments endpoints, and that the server
  enforces the check-in window itself (so the bot never has to parse a date
  out of a title - it just tries the reply and handles `423`).
- Wrote `practice_hub_client.py`, `collect.py`, `checkin.py`, and `main.py`.
- Wrote the GitHub Actions workflow (`checkin-bot.yml`).
- Diagnosed a local-machine-only SSL failure (Avast's HTTPS-scanning proxy
  injects a root certificate that Python's `certifi` bundle doesn't trust,
  even though `curl` trusts it via the Windows store) and built a temporary
  local CA bundle to test against the live API - this only affected testing
  on this machine and isn't part of the deployed bot or its dependencies.
- Ran the bot against the live Practice Hub API repeatedly while building
  it: verified Task 1's collected bodies/attachments byte-for-byte against a
  fresh re-download, and verified Task 2's duplicate-reply guard by running
  it twice in a row.
- Wrote this README.

**What I decided:**

- The exact wording of the check-in reply ("Alex Crenshaw checking in -
  `<UTC timestamp>`") - I asked for this specific phrasing.
- When to actually post the real reply to the day's open check-in during
  development, since posting is a visible action on the instructor's post -
  I approved that before it ran.
- Reviewed the plan (repo layout, cron schedule/reasoning, commit
  structure) before any code was written, and reviewed the diffs/output as
  each piece landed.

**What I changed:**

- Had Claude fix a bug it introduced: attachment `local_path` values in
  `collected.json` were using Windows backslashes from a local test run;
  fixed to always use forward slashes so the JSON is consistent regardless
  of what OS produced it (matters since GitHub Actions runs on Ubuntu).
- Added a `.gitattributes` entry (`artifact/files/** -text`) after noticing
  git's line-ending normalization would have altered the downloaded text
  attachments on commit - verified the fix by diffing a fresh download
  against the committed file.
