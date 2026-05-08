#!/usr/bin/env python3
"""Export Granola meeting notes and transcripts to Markdown files with YAML frontmatter."""

import argparse
import gzip
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


GRANOLA_ACCOUNTS = Path.home() / "Library" / "Application Support" / "Granola" / "stored-accounts.json"
STATE_FILE_NAME = ".granola-export-state.json"


def get_access_token() -> str | None:
    if not GRANOLA_ACCOUNTS.exists():
        return None
    with open(GRANOLA_ACCOUNTS, "r") as f:
        data = json.load(f)
    accounts = json.loads(data.get("accounts", "[]"))
    if not accounts:
        return None
    tokens = json.loads(accounts[0].get("tokens", "{}"))
    return tokens.get("access_token")


def api_call(access_token: str, endpoint: str, payload: dict) -> any:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
    }
    url = f"https://api.granola.ai/v1/{endpoint}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=30)
    raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def sanitize_filename(title: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized[:100]


def prosemirror_to_markdown(doc: dict) -> str:
    if not doc or not isinstance(doc, dict):
        return ""
    content = doc.get("content", [])
    lines = []
    for block in content:
        block_type = block.get("type", "")
        inner_content = block.get("content", [])
        text = "".join(node.get("text", "") for node in inner_content if node.get("type") == "text")

        if block_type == "heading":
            level = block.get("attrs", {}).get("level", 1)
            if text:
                lines.append(f"{'#' * level} {text}")
                lines.append("")
        elif block_type == "paragraph":
            lines.append(text)
            lines.append("")
        elif block_type == "bulletList":
            for item in block.get("content", []):
                item_lines = extract_list_item_text(item)
                if item_lines:
                    lines.append(f"- {item_lines[0]}")
                    lines.extend(item_lines[1:])
            lines.append("")
        elif block_type == "orderedList":
            for i, item in enumerate(block.get("content", []), 1):
                item_lines = extract_list_item_text(item)
                if item_lines:
                    lines.append(f"{i}. {item_lines[0]}")
                    lines.extend(item_lines[1:])
            lines.append("")
        elif block_type == "blockquote":
            for child in block.get("content", []):
                child_content = child.get("content", [])
                child_text = "".join(n.get("text", "") for n in child_content if n.get("type") == "text")
                lines.append(f"> {child_text}")
            lines.append("")
        elif block_type == "codeBlock":
            lines.append("```")
            lines.append(text)
            lines.append("```")
            lines.append("")
        elif block_type == "horizontalRule":
            lines.append("---")
            lines.append("")
        else:
            if text:
                lines.append(text)
                lines.append("")

    result = "\n".join(lines)
    return re.sub(r'\n{3,}', '\n\n', result).strip()


def extract_list_item_text(item: dict, indent: int = 0) -> list[str]:
    lines = []
    for child in item.get("content", []):
        child_type = child.get("type", "")
        if child_type == "paragraph":
            text = "".join(n.get("text", "") for n in child.get("content", []) if n.get("type") == "text")
            prefix = "  " * indent + "- " if indent > 0 else ""
            if indent == 0:
                lines.append(text)
            else:
                lines.append(prefix + text)
        elif child_type == "bulletList":
            for sub_item in child.get("content", []):
                lines.extend(extract_list_item_text(sub_item, indent + 1))
        elif child_type == "orderedList":
            for i, sub_item in enumerate(child.get("content", []), 1):
                sub_lines = extract_list_item_text(sub_item, indent + 1)
                if sub_lines:
                    sub_lines[0] = "  " * (indent + 1) + f"{i}. " + sub_lines[0].lstrip(" -")
                lines.extend(sub_lines)
    if not lines:
        text = ""
        for child in item.get("content", []):
            for node in child.get("content", []):
                if node.get("type") == "text":
                    text += node.get("text", "")
        lines.append(text)
    return lines


def get_note_content(doc: dict) -> str:
    md = doc.get("notes_markdown", "")
    if md and md.strip():
        return md.strip()
    notes = doc.get("notes")
    if notes:
        converted = prosemirror_to_markdown(notes)
        if converted:
            return converted
    plain = doc.get("notes_plain", "")
    if plain and plain.strip():
        return plain.strip()
    return ""


def yaml_escape(value: str) -> str:
    if any(c in value for c in ':{}[],"\'|>&*!#%@`'):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def build_note_frontmatter(doc: dict) -> str:
    lines = ["---"]
    lines.append(f"title: {yaml_escape(doc.get('title', 'Untitled'))}")
    lines.append(f"date: {doc.get('created_at', '')}")
    lines.append(f"updated: {doc.get('updated_at', '')}")

    doc_type = doc.get("type")
    if doc_type:
        lines.append(f"type: {doc_type}")

    people = doc.get("people")
    if people and isinstance(people, dict):
        attendee_list = []
        creator = people.get("creator")
        if creator:
            name = creator.get("name", "")
            email = creator.get("email", "")
            if name and email:
                attendee_list.append(f"{name} <{email}>")
            elif email:
                attendee_list.append(email)
        for att in people.get("attendees", []):
            name = ""
            details = att.get("details", {})
            if details and details.get("person"):
                name_info = details["person"].get("name", {})
                name = name_info.get("fullName", "") if isinstance(name_info, dict) else ""
            email = att.get("email", "")
            if name and email:
                attendee_list.append(f"{name} <{email}>")
            elif email:
                attendee_list.append(email)
        if attendee_list:
            lines.append("attendees:")
            for a in attendee_list:
                lines.append(f"  - {yaml_escape(a)}")

    cal = doc.get("google_calendar_event")
    if cal:
        start = cal.get("start", {})
        end = cal.get("end", {})
        if start.get("dateTime"):
            lines.append(f"calendar_start: {start['dateTime']}")
        if end.get("dateTime"):
            lines.append(f"calendar_end: {end['dateTime']}")
        location = cal.get("location")
        if location:
            lines.append(f"calendar_location: {yaml_escape(location)}")

    source = doc.get("creation_source")
    if source:
        lines.append(f"source: {source}")

    lines.append(f"granola_id: {doc.get('id', '')}")
    lines.append("---")
    return "\n".join(lines)


def build_transcript_frontmatter(doc: dict, entries: list) -> str:
    lines = ["---"]
    lines.append(f"title: {yaml_escape(doc.get('title', 'Untitled'))}")
    lines.append(f"date: {doc.get('created_at', '')}")
    lines.append(f"granola_id: {doc.get('id', '')}")

    if entries:
        first_ts = entries[0].get("start_timestamp", "")
        last_ts = entries[-1].get("end_timestamp", "")
        if first_ts and last_ts:
            try:
                t_start = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t_end = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                duration = int((t_end - t_start).total_seconds() / 60)
                lines.append(f"duration_minutes: {duration}")
            except (ValueError, TypeError):
                pass
        lines.append(f"entry_count: {len(entries)}")

    lines.append("---")
    return "\n".join(lines)


def format_transcript(entries: list) -> str:
    lines = []
    for entry in entries:
        ts = entry.get("start_timestamp", "")
        text = entry.get("text", "")
        source = entry.get("source", "unknown")

        time_str = ""
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except (ValueError, TypeError):
                time_str = ts

        source_label = "mic" if source == "microphone" else source
        lines.append(f"**[{time_str}] ({source_label}):** {text}")
        lines.append("")

    return "\n".join(lines).strip()


def get_doc_date_prefix(doc: dict) -> str:
    created = doc.get("created_at", "")
    if created:
        return created[:10]
    return "unknown-date"


def download_attachments(attachments: list, attachments_dir: Path, doc_id: str) -> list[str]:
    downloaded = []
    for i, att in enumerate(attachments):
        if att.get("type") != "image":
            continue
        url = att.get("url", "")
        if not url:
            continue
        ext = ".png"
        if "jpg" in url or "jpeg" in url:
            ext = ".jpg"
        filename = f"{doc_id}_{i}{ext}"
        filepath = attachments_dir / filename
        if not filepath.exists():
            try:
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=30)
                filepath.write_bytes(resp.read())
            except Exception:
                continue
        downloaded.append(filename)
    return downloaded


def load_state(output_dir: Path) -> dict:
    state_path = output_dir / STATE_FILE_NAME
    if state_path.exists():
        with open(state_path, "r") as f:
            return json.load(f)
    return {}


def save_state(output_dir: Path, state: dict):
    state_path = output_dir / STATE_FILE_NAME
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Export Granola meeting notes to Markdown")
    parser.add_argument("--output", "-o", type=str, required=True, help="Output directory (Obsidian vault path)")
    parser.add_argument("--granola-dir", type=str, default="granola", help="Top-level folder inside output directory")
    parser.add_argument("--notes-dir", type=str, default="notes", help="Subfolder for notes")
    parser.add_argument("--transcripts-dir", type=str, default="transcripts", help="Subfolder for transcripts")
    parser.add_argument("--attachments-dir", type=str, default="attachments", help="Subfolder for downloaded images")
    parser.add_argument("--full", action="store_true", help="Force full export (ignore last export timestamp)")
    parser.add_argument("--no-summary", action="store_true", help="Skip fetching AI summaries from Granola API")
    parser.add_argument("--no-transcript", action="store_true", help="Skip fetching transcripts")
    args = parser.parse_args()

    output_dir = Path(args.output).expanduser().resolve()
    granola_dir = output_dir / args.granola_dir
    notes_dir = granola_dir / args.notes_dir
    transcripts_dir = granola_dir / args.transcripts_dir
    attachments_dir = granola_dir / args.attachments_dir

    notes_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir.mkdir(parents=True, exist_ok=True)

    access_token = get_access_token()
    if not access_token:
        print("Error: Could not load access token from Granola.")
        print("  Ensure Granola is running and you are signed in.")
        return 1

    print("Fetching documents from Granola API...")
    try:
        documents = api_call(access_token, "get-documents", {"limit": 200})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("Error: Access token expired. Open Granola to refresh it.")
        else:
            print(f"Error fetching documents: {e.code} {e.reason}")
        return 1

    if not isinstance(documents, list):
        print(f"Error: Unexpected response from API")
        return 1

    print(f"  Found {len(documents)} documents")

    export_state = load_state(granola_dir)
    last_export = export_state.get("last_export_timestamp", "")

    if args.full:
        last_export = ""

    notes_exported = 0
    transcripts_exported = 0
    summaries_fetched = 0
    skipped = 0

    for doc in documents:
        doc_id = doc.get("id", "")
        updated_at = doc.get("updated_at", "")

        if last_export and updated_at and updated_at <= last_export:
            skipped += 1
            continue

        title = doc.get("title") or "Untitled"
        date_prefix = get_doc_date_prefix(doc)
        filename = f"{date_prefix} - {sanitize_filename(title)}.md"

        content = get_note_content(doc)
        frontmatter = build_note_frontmatter(doc)

        summary_md = ""
        if not args.no_summary:
            try:
                panels = api_call(access_token, "get-document-panels", {"document_id": doc_id})
                if isinstance(panels, list):
                    for panel in panels:
                        panel_content = panel.get("content")
                        if panel_content:
                            panel_md = prosemirror_to_markdown(panel_content)
                            if panel_md:
                                summary_md = panel_md
                                summaries_fetched += 1
                                break
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    print(f"  Auth expired fetching summary for: {title}")
                    args.no_summary = True
            except Exception as e:
                print(f"  Warning: Failed to fetch summary for: {title} ({e})")

        attachments = doc.get("attachments") or []
        image_filenames = []
        if attachments:
            image_filenames = download_attachments(attachments, attachments_dir, doc_id)

        rel_attachments = f"../{args.attachments_dir}"
        note_path = notes_dir / filename
        with open(note_path, "w") as f:
            f.write(frontmatter)
            f.write("\n\n")
            if image_filenames:
                f.write("## Attachments\n\n")
                for img in image_filenames:
                    f.write(f"![{img}]({rel_attachments}/{img})\n\n")
            if summary_md:
                f.write("## Summary\n\n")
                f.write(summary_md)
                f.write("\n\n")
                if content:
                    f.write("---\n\n")
                    f.write("## Notes\n\n")
                    f.write(content)
            elif content:
                f.write(content)
            else:
                f.write("*No notes recorded*")
            f.write("\n")
        notes_exported += 1

        if not args.no_transcript:
            try:
                transcript = api_call(access_token, "get-document-transcript", {"document_id": doc_id})
                if isinstance(transcript, list) and transcript:
                    t_frontmatter = build_transcript_frontmatter(doc, transcript)
                    t_content = format_transcript(transcript)
                    t_path = transcripts_dir / filename

                    with open(t_path, "w") as f:
                        f.write(t_frontmatter)
                        f.write("\n\n")
                        f.write(t_content)
                        f.write("\n")
                    transcripts_exported += 1
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    print(f"  Auth expired fetching transcript for: {title}")
                    args.no_transcript = True
            except Exception as e:
                print(f"  Warning: Failed to fetch transcript for: {title} ({e})")

    if notes_exported > 0 or transcripts_exported > 0:
        now = datetime.now(timezone.utc).isoformat()
        export_state["last_export_timestamp"] = now
        export_state["last_export_notes_count"] = notes_exported
        export_state["last_export_transcripts_count"] = transcripts_exported
        save_state(granola_dir, export_state)

    print(f"Export complete:")
    print(f"  Notes exported: {notes_exported}")
    print(f"  Summaries fetched: {summaries_fetched}")
    print(f"  Transcripts exported: {transcripts_exported}")
    print(f"  Skipped (unchanged): {skipped}")
    print(f"  Output: {granola_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
