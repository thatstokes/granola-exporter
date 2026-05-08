# Granola Exporter

![AI-Generated License Badge](vibe-coded-badge.svg)


Export your [Granola](https://granola.ai) meeting notes, AI summaries, and transcripts to Markdown files with YAML frontmatter — perfect for Obsidian or any Markdown-based knowledge base.

## Requirements

- Python 3.10+
- macOS (reads auth tokens from the Granola desktop app)
- Granola desktop app installed and signed in

No pip dependencies — stdlib only.

## Installation

```bash
git clone git@github.com:thatstokes/granola-exporter.git
cd granola-exporter
```

The script is already marked executable, so you can run it directly — no `pip install` or virtual environment needed.

## Usage

```bash
./export_granola.py --output ~/path/to/obsidian/vault
```

This will:
1. Fetch all your meeting documents from Granola's API
2. Export notes with AI-generated summaries to `granola-notes/`
3. Export full transcripts to `granola-transcripts/`
4. Track what was exported so the next run only processes new/updated meetings

### First run

Use `--full` to export everything:

```bash
python3 export_granola.py --output ./my-notes --full
```

### Subsequent runs

Just run without `--full` — only new or updated meetings will be exported:

```bash
python3 export_granola.py --output ./my-notes
```

## Options

| Flag | Description |
|------|-------------|
| `--output`, `-o` | Output directory (required) |
| `--full` | Force full export, ignoring last export timestamp |
| `--no-summary` | Skip fetching AI-generated summaries |
| `--no-transcript` | Skip fetching transcripts |
| `--granola-dir` | Top-level folder inside output directory (default: `granola`) |
| `--notes-dir` | Subfolder name for notes (default: `notes`) |
| `--transcripts-dir` | Subfolder name for transcripts (default: `transcripts`) |
| `--attachments-dir` | Subfolder name for downloaded images (default: `attachments`) |

## Output structure

```
output/
└── granola/
    ├── notes/
    │   ├── 2026-05-07 - Weekly Team Sync.md
    │   ├── 2026-05-06 - Product Review.md
    │   └── ...
    ├── transcripts/
    │   ├── 2026-05-07 - Weekly Team Sync.md
    │   ├── 2026-05-06 - Product Review.md
    │   └── ...
    ├── attachments/
    │   ├── abc123-def456_0.png
    │   └── ...
    └── .granola-export-state.json
```

### Note format

```markdown
---
title: Weekly Team Sync
date: 2026-05-07T18:00:00.000Z
updated: 2026-05-07T19:30:00.000Z
type: meeting
attendees:
  - "Jane Smith <jane@company.com>"
  - "Bob Jones <bob@company.com>"
calendar_start: 2026-05-07T14:00:00-04:00
calendar_end: 2026-05-07T14:30:00-04:00
calendar_location: "Conference Room A"
source: macOS
granola_id: abc123-def456
---

## Attachments

![abc123-def456_0.png](../attachments/abc123-def456_0.png)

## Summary

### Key Decisions
- Approved the new timeline for Q3 launch
- Agreed to weekly standups starting next Monday

### Action Items
- Jane: Draft the proposal by Friday
- Bob: Set up the staging environment

---

## Notes

My own notes taken during the meeting appear here.
```

### Transcript format

```markdown
---
title: Weekly Team Sync
date: 2026-05-07T18:00:00.000Z
granola_id: abc123-def456
duration_minutes: 32
entry_count: 847
---

**[18:00:03] (mic):** Alright let's get started.

**[18:00:05] (system):** Good morning everyone.

**[18:00:12] (mic):** First item on the agenda is the Q3 timeline.
```

## Authentication

The script reads the access token from:
```
~/Library/Application Support/Granola/stored-accounts.json
```

This file is maintained by the Granola desktop app. Tokens expire after ~6 hours and are refreshed automatically while Granola is running.

If you get a 401 error, open the Granola app to refresh the token, then re-run the script.

## Automation

To run on a schedule (e.g., end of each workday), add a cron job or launchd plist:

```bash
# Export new notes every day at 6pm
0 18 * * 1-5 /usr/bin/python3 /path/to/export_granola.py --output ~/Obsidian/Meetings
```

Note: Granola must have been open at some point during the day for the token to be valid.
