# Granola Exporter

## What this is

A Python script that exports meeting notes, AI-generated summaries, and transcripts from [Granola](https://granola.ai) into Markdown files with YAML frontmatter, intended for use with Obsidian.

## Architecture

The script is entirely API-driven. It authenticates using the access token stored locally by the Granola desktop app at `~/Library/Application Support/Granola/stored-accounts.json`.

### API endpoints used

- `POST https://api.granola.ai/v1/get-documents` — fetches all documents (notes, metadata, calendar events, attendees)
- `POST https://api.granola.ai/v1/get-document-panels` — fetches AI-generated summary panels for a document
- `POST https://api.granola.ai/v1/get-document-transcript` — fetches raw transcript entries for a document

Auth is Bearer token in the Authorization header. No special client headers needed.

### Token management

The Granola Electron app maintains a valid WorkOS access token in `stored-accounts.json`. Tokens expire after ~6 hours. The app refreshes them automatically while running. If the token is expired, the user needs to open Granola to trigger a refresh.

There was previously a `cache-v6.json` local cache file approach, but Granola switched to encrypting that file (`cache-v6.json.enc`), making the API the only reliable data source.

### Content format

Granola stores rich text as ProseMirror JSON (`{type: "doc", content: [{type: "heading"|"paragraph"|"bulletList", ...}]}`). The script converts this to Markdown via `prosemirror_to_markdown()`. This handles headings, paragraphs, bullet lists (nested), ordered lists, blockquotes, code blocks, and horizontal rules.

### Incremental export

A `.granola-export-state.json` file in the output directory tracks `last_export_timestamp`. On subsequent runs, documents whose `updated_at` is older than this timestamp are skipped. The timestamp only advances when something is actually exported.

## Key decisions

- No dependencies beyond Python 3 stdlib
- macOS only (Granola token path is macOS-specific)
- Filenames are `{date} - {sanitized title}.md`
- Notes include the AI summary under `## Summary` followed by user notes under `## Notes` (separated by `---`)
- Transcripts are formatted as `**[HH:MM:SS] (source):** text` with one entry per line
