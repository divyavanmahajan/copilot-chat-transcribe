# Specification: M365 Copilot Chat Transcript Formatter

## Overview

A Python command-line tool that converts a Microsoft 365 Copilot chat export (JSON) into a clean, readable, self-contained HTML file — inspired by the presentation style of [simonw/claude-code-transcripts](https://github.com/simonw/claude-code-transcripts).

## Goals

- Accept any M365 Copilot JSON export file as input
- Produce a single self-contained `.html` file (all CSS/JS inline)
- Render markdown in assistant responses as formatted HTML
- Display embedded images inline
- Present a clear visual distinction between user and assistant turns
- Be usable without any installed web server

## Non-Goals

- Pagination (the expected chats are short; single page is sufficient)
- Publishing to GitHub Gist or other sharing services
- Support for JSONL format (M365 exports are JSON)
- Round-trip editing of transcripts

## Input

A JSON file exported from Microsoft 365 Copilot (Bing Chat / M365 Copilot via browser). The file has this top-level structure:

```
store.rawConversationResponse.messages[]
```

### Message types (by `author` field)

| Author   | Description                                    | Display              |
|----------|------------------------------------------------|----------------------|
| `user`   | Human turn — plain text, may include file refs | Shown                |
| `bot`    | Assistant turn — markdown text                 | Shown (rendered)     |
| `system` | Internal system prompt (`messageType: Internal`) | Hidden             |

## Output

A single `.html` file with:

1. **Header** — session title (first user message, truncated) and date range
2. **Conversation thread** — alternating user/assistant message bubbles with:
   - Author label and formatted timestamp
   - Rendered markdown (for bot messages)
   - Plain text (for user messages), with `<entity>` refs stripped or replaced with filenames
   - Inline image previews (from `messageAnnotations`)
3. **Self-contained** — all CSS and minimal JS embedded in `<style>` and `<script>` tags; no external dependencies at runtime

## CLI Interface

```
# From a local JSON file (prompts for folder name, default = filename stem)
python format_chat.py <input.json> [-o output-folder] [--open]

# From live browser via Playwright CDP
python format_chat.py --connect [--cdp-url http://localhost:9222] [-o folder] [--open]
```

| Flag/Arg        | Description                                                       |
|-----------------|-------------------------------------------------------------------|
| `input.json`    | Path to M365 Copilot JSON export (mutually exclusive with --connect) |
| `--connect`     | Connect to MSEdge on port 9222 and browse conversations interactively |
| `--cdp-url URL` | Override CDP endpoint (default: `http://localhost:9222`)          |
| `-o / --output` | Output folder path (prompted if omitted)                          |
| `--open`        | Open `transcript.html` in the default browser after writing       |

## Output Folder

Every run writes a folder containing three files:

| File | Description |
|------|-------------|
| `transcript.html` | Self-contained styled HTML with rendered markdown, inline images |
| `transcript.md` | Plain markdown, no images (suitable for note-taking tools) |
| `conversation.json` | Original JSON export (copied or downloaded) |

Default folder name:
- File mode: the input filename stem (e.g. `5d41e7f4-...`)
- Connect mode: the conversation ID (e.g. `5d41e7f4-5156-4a60-819c-c38184df70aa`)
- User is always prompted to confirm or override the default

## Visual Design (inspired by simonw)

- Clean white background, system font stack
- Max-width container (~800px), centered
- **User messages**: right-aligned, distinct background (e.g. light blue)
- **Assistant messages**: left-aligned, white/light grey with subtle border
- Message header: role label + timestamp (ISO → human-readable)
- Timestamps are `<time>` elements with `datetime` attribute
- Inline images: max-width 100%, rounded corners
- Code blocks: monospace, syntax-highlighted background (no external lib needed)
- Mobile-friendly via `viewport` meta and responsive CSS

