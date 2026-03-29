# copilot-chat-transcribe

Convert **Microsoft 365 Copilot** chat sessions into clean, readable transcripts —
a styled HTML file you can open in any browser, and a plain Markdown file for note-taking apps.

Two modes:

| Mode | When to use |
|------|-------------|
| **File mode** | You already have a JSON export from the browser |
| **`--connect` mode** | Let the tool fetch the conversation live from your signed-in Edge browser |

---

## Installation

```bash
pip install copilot-chat-transcribe
```

For **`--connect` mode** (live browser download via Playwright):

```bash
pip install "copilot-chat-transcribe[connect]"
playwright install msedge
```

### No-install option (uv / uvx)

```bash
# one-off run
uvx --from copilot-chat-transcribe copilot-chat-transcribe --help

# with --connect support
uvx --from "copilot-chat-transcribe[connect]" copilot-chat-transcribe --connect
```

---

## Quick start

### Mode 1 — convert a JSON file

```bash
copilot-chat-transcribe conversation.json
```

You will be asked for an output folder name (the filename stem is suggested as the default).
Skip the prompt by passing `-o`:

```bash
copilot-chat-transcribe conversation.json -o my-chat
```

Three files are written into the folder:

```
my-chat/
├── transcript.html    ← open in any browser
├── transcript.md      ← paste into Obsidian, Notion, etc.
└── conversation.json  ← original export, archived alongside
```

Open the HTML automatically when done:

```bash
copilot-chat-transcribe conversation.json -o my-chat --open
```

---

### Mode 2 — live download (`--connect`)

This mode connects to your already-running **Microsoft Edge** browser using its
remote debugging interface, so it can read your signed-in Copilot session without
you needing to copy any cookies or tokens.

```bash
copilot-chat-transcribe --connect
```

**Step-by-step walkthrough:**

1. The tool checks whether Edge is already listening on port 9222.
2. If not, it asks:
   ```
   MSEdge not found on port 9222. Start it now? [Y/n]
   ```
   Press **Enter** (or `Y`) to launch Edge automatically with remote debugging enabled.
3. Edge opens at `chat.cloud.microsoft`. Sign in if needed, then press **Enter** in the terminal.
4. The tool fetches your latest 10 conversations and shows a numbered list:
   ```
   Latest 10 conversations:
    1. Python data pipeline question  (2026-03-28 14:32)
    2. Draft email to team            (2026-03-27 09:11)
    ...
   Select conversation [1]: 
   ```
5. Press **Enter** to accept the default (most recent) or type a number.
6. The conversation is downloaded, parsed, and written to the output folder.

Specify the output folder and open immediately:

```bash
copilot-chat-transcribe --connect -o my-chat --open
```

#### Starting Edge manually instead

If you prefer to start Edge yourself before running the tool:

**Windows:**
```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

**macOS:**
```bash
/Applications/Microsoft\ Edge.app/Contents/MacOS/Microsoft\ Edge --remote-debugging-port=9222
```

Then run `copilot-chat-transcribe --connect` as normal.

---

## All options

```
copilot-chat-transcribe [-h] [--connect | input] [-o FOLDER] [--cdp-url URL] [--open] [--version]
```

| Flag | Default | Description |
|------|---------|-------------|
| `input` | *(positional)* | Path to a M365 Copilot JSON export file |
| `--connect` | — | Enable live browser download mode |
| `-o / --output FOLDER` | *(prompted)* | Output folder path |
| `--cdp-url URL` | `http://localhost:9222` | Chrome DevTools Protocol endpoint |
| `--open` | off | Open `transcript.html` in the default browser when done |
| `--version` | — | Print version and exit |

`input` and `--connect` are mutually exclusive — use one or the other.

---

## Output format

### `transcript.html`

- **Self-contained** — one file, no internet connection needed, works offline
- **User messages** — right-aligned blue speech bubbles
- **Copilot responses** — left-aligned, rendered Markdown (headings, tables, code blocks with syntax highlighting)
- **Images** — attached files embedded as inline base64 `<img>` tags
- **Timestamps** — stored as UTC in the HTML, converted to your local time by the browser

### `transcript.md`

- `## You` / `## Copilot` headers separate each turn
- Copilot responses are reproduced in their original Markdown
- Images are not embedded (the filename is noted as a placeholder)
- Suitable for pasting into Obsidian, Notion, Confluence, or any Markdown editor

---

## Where does the JSON come from? (File mode)

If you want to export a conversation yourself without `--connect`:

1. Open `chat.cloud.microsoft` in Edge or Chrome
2. Open DevTools → **Network** tab
3. Start a conversation or reload the page
4. Filter requests by `conversation` — look for a `GET` request to  
   `https://m365.cloud.microsoft/chat/conversation/<uuid>`
5. Right-click the request → **Copy → Copy response**
6. Paste into a `.json` file and run `copilot-chat-transcribe that-file.json`

---

## Troubleshooting

### `Error: Playwright is required for --connect mode`

Install the connect extra:

```bash
pip install "copilot-chat-transcribe[connect]"
playwright install msedge
```

### Edge opens but the tool can't connect

Make sure Edge was launched **with** the debugging flag.  
If Edge was already running before you ran the tool, close it fully (check the system tray)
and let the tool start it, or start it manually with `--remote-debugging-port=9222`.

### `UnicodeEncodeError` on Windows

Set the terminal encoding before running:

```powershell
$env:PYTHONIOENCODING = "utf-8"
copilot-chat-transcribe conversation.json -o out
```

Or permanently in your PowerShell profile.

### The conversation list is empty

The tool fetches the 10 most recent conversations from the Copilot nav pane API.
Make sure you are signed in to `chat.cloud.microsoft` in the browser window that Edge opened.

---

## Development

```bash
git clone https://github.com/your-org/copilot-chat-transcribe
cd copilot-chat-transcribe
uv venv
uv pip install -e ".[connect]"
playwright install msedge
copilot-chat-transcribe --help
```

Run against a sample file:

```bash
copilot-chat-transcribe path/to/export.json -o test-out --open
```

---

## License

MIT


