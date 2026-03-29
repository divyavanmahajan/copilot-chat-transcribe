# Architecture

## Overview

```
input JSON / --connect
    │
    ├─[file mode]──────────────────────────────────────────────────────────┐
    │   parse_file(path)                                                    │
    │                                                                       │
    └─[--connect mode]─────────────────────────────────────────────────────┤
        connector.py                                                        │
          connect(cdp_url) → Playwright attaches to running MSEdge          │
          list_conversations(page)                                           │
            └─ expect_response(RefreshNavPane POST) set up BEFORE goto      │
               page.goto(CHAT_BASE_URL) → SPA fires nav-pane POST          │
               → intercept response → list of up to 50 chats               │
          prompt_select_conversation(page)                                   │
            └─ shows 10 at a time; user types number or m/more             │
          download_conversation(page, conv_id)                              │
            └─ expect_response(GET /conversation/{id}) set up BEFORE goto  │
               page.goto(conversation URL) → SPA fires data XHR            │
               → intercept JSON response (fallback: page.evaluate fetch)   │
          parse_file(tmp_json)                                              │
                                                                            ▼
                                                           ┌─────────────────────┐
                                                           │  Conversation model  │
                                                           └──────────┬──────────┘
                                                                      │
                                                           ┌──────────▼──────────┐
                                                           │    renderer.py        │
                                                           │  render() → HTML      │
                                                           │  render_markdown_doc()│
                                                           └──────────┬──────────┘
                                                                      │
                                                           ┌──────────▼──────────┐
                                                           │   output folder/      │
                                                           │     transcript.html   │
                                                           │     transcript.md     │
                                                           │     conversation.json │
                                                           └─────────────────────┘
```

The tool is intentionally simple: **no web framework, no template engine, no external CSS/JS libraries**. All HTML is produced by Python string formatting / f-strings within `renderer.py`. The only required third-party dependency is `markdown`; `playwright` is optional (install `copilot-chat-transcribe[connect]`).

---

## Module Responsibilities

### `cli.py` — CLI entry point (`copilot-chat-transcribe` command)

- Parses CLI arguments (`argparse`): two mutually exclusive modes (`input` file or `--connect`)
- **File mode**: calls `parser.parse_file(path)` → `Conversation`
- **Connect mode**: calls `connector.connect()`, `connector.prompt_select_conversation()`, `connector.download_conversation()`, then `parse_file(tmp)` → `Conversation`
- Prompts for output folder name if `--output` not specified
- Calls `renderer.render()` and `renderer.render_markdown_doc()`, writes three output files
- Optionally opens `transcript.html` in the default browser

### `parser.py` — JSON → data model

1. Load and validate the JSON file
2. Extract `store.rawConversationResponse.messages`
3. Build a lookup of entity references from `store.zeroQuery.data.items[].hydratedEntities`
4. For each message:
   - Skip messages where `author == "system"` or `messageType == "Internal"`
   - Parse `createdAt` into a `datetime` object
   - Substitute `<entity ...>` tags in user message text with resolved filenames
   - Extract `messageAnnotations` → list of `Attachment`
5. Return a `Conversation` dataclass

### `renderer.py` — data model → HTML + Markdown

1. `render(conv)` → complete self-contained HTML document (CSS + JS inlined)
2. `render_markdown_doc(conv)` → clean Markdown with `## You` / `## Copilot` headers, no images

### `connector.py` — Playwright browser bridge

1. `_ensure_cdp_available(cdp_url)` — checks port 9222; offers to start MSEdge if closed
2. `connect(cdp_url)` → attaches to running MSEdge via CDP; returns `(playwright, browser, page)`
3. `list_conversations(page, limit=50)` → registers `expect_response` **before** `page.goto(CHAT_BASE_URL)`; filters on `RefreshNavPane` in POST body; returns list of chat dicts
4. `download_conversation(page, conv_id)` → registers `expect_response` **before** `page.goto(conversation URL)`; filters on `application/json` content-type; falls back to `page.evaluate(fetch(...))` with `credentials: "include"` + `crypto.randomUUID()` for `x-session-id`
5. `prompt_select_conversation(page, page_size=10)` → pages through chats 10 at a time; user types a number or `m`/`more` to advance

**Key design**: response interception via Playwright's `expect_response` — the listener is always registered *before* navigation so the SPA's boot-time API calls are captured without needing to re-trigger them. Auth is inherited from the browser's cookie jar automatically.

---

## File Layout

```
chat/
├── src/copilot_chat/
│   ├── __init__.py      # __version__
│   ├── models.py        # Attachment, Message, Conversation dataclasses
│   ├── parser.py        # JSON → Conversation
│   ├── renderer.py      # Conversation → HTML + Markdown
│   ├── connector.py     # Playwright CDP bridge + Edge auto-start
│   └── cli.py           # copilot-chat-transcribe entry point
├── examples/
│   └── demo_parse.py    # parse walkthrough (uses installed package)
├── docs/
│   ├── spec.md
│   ├── architecture.md
│   ├── data-model.md
│   ├── implementation-plan.md
│   ├── progress.md
│   └── demo.md          # Showboat walkthrough
├── logs/                # captured API request/response samples
├── pyproject.toml       # hatchling build, entry point, dependencies
├── README.md
└── .gitignore
```

---

## Key Design Decisions

### Listener-before-navigation interception
`page.expect_response(predicate)` is entered as a context manager *before* `page.goto()` so Playwright's internal event waiter is active from the moment navigation starts. This captures responses that arrive during page boot without needing a separate reload step.

### RefreshNavPane POST filtering
The SPA makes several POSTs to the same base URL during initialisation. The predicate filters on `"RefreshNavPane" in response.request.post_data` so only the nav-pane response (which carries the conversation list) is captured.

### download_conversation fallback
Some Edge configurations serve the conversation page with different URL patterns for the data XHR. If `expect_response` times out, a `page.evaluate(fetch(...))` call is made with `credentials: "include"` so auth cookies are inherited, plus the required `x-route-id: chat-history` and a generated `x-session-id`.

### Single self-contained HTML output
All CSS and JS are inlined. The output file can be opened directly from disk without any server, moved anywhere, and shared as a single attachment.

### No Jinja2 / no template engine
Python f-strings and helper functions in `renderer.py` are sufficient. This avoids a template engine dependency.

### `markdown` library for bot text
The `markdown` package (pure Python, BSD licensed) handles CommonMark-style markdown including headings, bold, italic, code fences, and tables — all of which appear in M365 Copilot responses.

### `adaptiveCards` ignored
The `adaptiveCards` field on bot messages duplicates the `text` field in a structured card format. Using `text` is simpler and already contains all content.

---

## CSS Design (inline in renderer)

- Max-width 820px, centred with `margin: 0 auto`
- System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`)
- User bubble: right-aligned flex item, `#0f6cbd` blue background, white text
- Bot bubble: left-aligned, `#f4f4f4` background, dark text
- Timestamps: small, muted colour, right-aligned in bubble header
- Code blocks: `#1e1e1e` dark background, `#d4d4d4` light text, monospace
- `<img>` inside messages: `max-width: 100%; border-radius: 6px`
- Fully responsive via `@media (max-width: 600px)` overrides

## JS (minimal, inline)

- Converts all `<time data-timestamp="ISO">` elements to locale-aware strings on page load — timestamps render in the viewer's local timezone
- No other JavaScript needed

```
input JSON / --connect
    │
    ├─[file mode]──────────────────────────────────────────────────────────┐
    │   parse_file(path)                                                    │
    │                                                                       │
    └─[--connect mode]─────────────────────────────────────────────────────┤
        connector.py                                                        │
          connect(cdp_url) → Playwright browser (existing MSEdge session)   │
          navigate_to_chat(page) → user confirms page loaded               │
          prompt_select_conversation(page) → user picks 1 of 10            │
            list_conversations(page) → in-browser fetch POST /chat         │
          download_conversation(page, conv_id) → in-browser fetch GET      │
          parse_file(tmp_json)                                              │
                                                                            ▼
                                                               ┌─────────────────────┐
                                                               │  Conversation model  │
                                                               └──────────┬──────────┘
                                                                          │
                                                               ┌──────────▼──────────┐
                                                               │    renderer.py        │
                                                               │  render() → HTML      │
                                                               │  render_markdown_doc()│
                                                               └──────────┬──────────┘
                                                                          │
                                                               ┌──────────▼──────────┐
                                                               │   output folder/      │
                                                               │     transcript.html   │
                                                               │     transcript.md     │
                                                               │     conversation.json │
                                                               └─────────────────────┘
```

The tool is intentionally simple: **no web framework, no template engine, no external CSS/JS libraries**. All HTML is produced by Python string formatting / f-strings within `renderer.py`. The only third-party dependency is `markdown` (for converting bot response text to HTML).

---

## Module Responsibilities

### `format_chat.py` — CLI entry point

- Parses CLI arguments (`argparse`): two mutually exclusive modes (`input` file or `--connect`)
- **File mode**: calls `parser.parse_file(path)` → `Conversation`
- **Connect mode**: calls `connector.connect()`, `navigate_to_chat()`, `prompt_select_conversation()`, `download_conversation()`, then `parse_file(tmp)` → `Conversation`
- Prompts for output folder name if `--output` not specified
- Calls `renderer.render()` and `renderer.render_markdown_doc()`, writes three output files
- Optionally opens `transcript.html` in the default browser

### `parser.py` — JSON → data model

Responsibilities:
1. Load and validate the JSON file
2. Extract `store.rawConversationResponse.messages`
3. Build a lookup of entity references from `store.zeroQuery.data.items[].hydratedEntities`
4. For each message:
   - Skip messages where `author == "system"` or `messageType == "Internal"`
   - Parse `createdAt` into a `datetime` object
   - Substitute `<entity ...>` tags in user message text with resolved filenames
   - Extract `messageAnnotations` → list of `Attachment`
5. Return a `Conversation` dataclass

### `renderer.py` — data model → HTML + Markdown

Responsibilities:
1. `render(conv)` → complete self-contained HTML document (CSS + JS inlined)
2. `render_markdown_doc(conv)` → clean Markdown with `## You` / `## Copilot` headers, no images

### `connector.py` — Playwright browser bridge

Responsibilities:
1. `connect(cdp_url)` → attaches to existing MSEdge via CDP; returns `(playwright, browser, page)`
2. `navigate_to_chat(page)` → ensures the chat page is open; waits for user confirmation
3. `list_conversations(page, limit)` → makes a POST fetch inside the browser to `/chat`; returns list of chat dicts
4. `download_conversation(page, conv_id)` → makes a GET fetch inside the browser to `/chat/conversation/{id}`; returns raw JSON
5. `prompt_select_conversation(page)` → CLI numbered list + user input; returns selected chat dict

**Key design**: all HTTP requests are executed via `page.evaluate(async () => fetch(...))` so they inherit the browser's existing auth cookies — no credential handling in Python.

---

## File Layout

```
chat/
├── format_chat.py       # CLI entry point
├── parser.py            # JSON parsing + normalisation
├── renderer.py          # HTML + Markdown generation
├── connector.py         # Playwright CDP browser connection + API calls
├── models.py            # dataclasses (Attachment, Message, Conversation)
├── docs/
│   ├── spec.md
│   ├── architecture.md
│   ├── data-model.md
│   ├── implementation-plan.md
│   ├── progress.md
│   └── demo.md          # Showboat walkthrough
└── 5d41e7f4-...json     # sample input file
```

---

## Key Design Decisions

### Single self-contained HTML output
All CSS and JS are inlined. The output file can be opened directly from disk without any server, moved anywhere, and shared as a single attachment.

### No Jinja2 / no template engine
Given the simplicity of the document structure, Python f-strings and helper functions in `renderer.py` are sufficient. This avoids a template engine dependency.

### `markdown` library for bot text
The `markdown` package (pure Python, BSD licensed) handles CommonMark-style markdown including headings, bold, italic, code fences, and lists — all of which appear in M365 Copilot responses. It is the only third-party dependency.

### `adaptiveCards` ignored
The `adaptiveCards` field on bot messages duplicates the `text` field in a structured card format. Using `text` is simpler and already contains all the content.

### Entity reference resolution
User messages may reference files with `<entity type='file' ReferenceId='...'>` tags. The tool performs a best-effort substitution — resolving to a filename from the `zeroQuery` section, falling back to `[file]`. The raw XML tags are never exposed in the output.

---

## CSS Design (inline in renderer)

- Max-width 820px, centred with `margin: 0 auto`
- System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`)
- User bubble: right-aligned flex item, `#0f6cbd` blue background, white text
- Bot bubble: left-aligned, `#f4f4f4` background, dark text
- Timestamps: small, muted colour, right-aligned in bubble header
- Code blocks: `#1e1e1e` dark background, `#d4d4d4` light text, monospace
- `<img>` inside messages: `max-width: 100%; border-radius: 6px`
- Fully responsive via `@media (max-width: 600px)` overrides

## JS (minimal, inline)

- Converts all `<time data-timestamp="ISO">` elements to locale-aware strings on page load — so timestamps render in the viewer's local timezone
- No other JavaScript needed

