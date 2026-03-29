# Implementation Plan

## Dependencies

| Package      | Purpose                          | Install                    |
|--------------|----------------------------------|----------------------------|
| `markdown`   | Render bot response markdown to HTML | `pip install markdown` |
| `playwright` | CDP browser control (`--connect` mode) | `pip install playwright` + `playwright install msedge` |

Standard library only for file mode: `json`, `argparse`, `dataclasses`, `datetime`, `re`, `html`, `pathlib`, `webbrowser`, `shutil`, `tempfile`.

---

## Milestones

### M1 — Models (`models.py`)

Define the three dataclasses used across all modules:

- `Attachment(file_name, file_type, data_uri)`
- `Message(message_id, author, text, created_at, turn, attachments)`
- `Conversation(messages, title, started_at, ended_at)`

**Done when:** dataclasses are importable with no errors.

---

### M2 — Parser (`parser.py`)

Implement `parse_file(path: Path) -> Conversation`:

1. `_load_json(path)` — read and validate; raise `ValueError` if `rawConversationResponse` is absent
2. `_build_entity_map(store)` — scan `zeroQuery.data.items[].hydratedEntities` and return `{referenceId: fileName}`
3. `_resolve_entities(text, entity_map)` — replace `<entity ...>text</entity>` with resolved filename using `re.sub`
4. `_parse_attachment(ann)` — map a raw annotation dict → `Attachment`; skip if `fileContent` missing
5. `_parse_message(raw, entity_map)` — map a raw message dict → `Message | None` (returns `None` for system messages)
6. `parse_file(path)` — orchestrate the above; build `Conversation` from the resulting message list

**Done when:** `parse_file("5d41e7f4-...json")` returns a `Conversation` with the correct number of non-system messages and at least one `Attachment`.

---

### M3 — Renderer (`renderer.py`)

Implement `render(conversation: Conversation) -> str`:

#### 3a. CSS constant
Write `CSS: str` at module level — the full stylesheet as a Python string. Cover:
- Container layout
- User and bot bubble styles
- Timestamp, author label
- `<img>` inside messages
- Code block styling
- Responsive breakpoints

#### 3b. JS constant
Write `JS: str` — the inline script that converts ISO timestamps to local strings:
```js
document.querySelectorAll('time[data-timestamp]').forEach(el => {
  el.textContent = new Date(el.dataset.timestamp).toLocaleString();
});
```

#### 3c. Message renderers
- `_render_attachment(att: Attachment) -> str` — returns `<figure><img ...><figcaption>...</figcaption></figure>`
- `_render_user_message(msg: Message) -> str` — escapes text, renders attachments, wraps in `.message.user`
- `_render_bot_message(msg: Message) -> str` — calls `markdown.markdown(msg.text)`, wraps in `.message.bot`
- `_render_message(msg: Message) -> str` — dispatches to user/bot renderer

#### 3d. Document assembly
- `_render_header(conv: Conversation) -> str` — `<header>` with title + date range
- `render(conv: Conversation) -> str` — full `<!DOCTYPE html>...<html>` document

**Done when:** `render(conversation)` produces valid HTML that opens correctly in a browser.

---

### M4 — CLI (`format_chat.py`)

```python
# format_chat.py
import argparse, webbrowser
from pathlib import Path
from parser import parse_file
from renderer import render

def main():
    p = argparse.ArgumentParser(description="Convert M365 Copilot chat JSON to HTML")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--open", action="store_true")
    args = p.parse_args()

    output = args.output or args.input.with_suffix(".html")
    conversation = parse_file(args.input)
    html = render(conversation)
    output.write_text(html, encoding="utf-8")
    print(f"Written: {output}")
    if args.open:
        webbrowser.open(output.resolve().as_uri())

if __name__ == "__main__":
    main()
```

**Done when:** `python format_chat.py 5d41e7f4-...json --open` opens a rendered transcript in the browser.

---

### M5 — Smoke test

Run against the sample file and verify:

- [ ] No Python errors or exceptions
- [ ] Output file is valid HTML (check with browser dev tools or `html.parser`)
- [ ] All 4 conversation turns visible (user + bot alternating)
- [ ] System messages absent from output
- [ ] At least one image rendered inline
- [ ] Bot responses display formatted headings, bullets, bold, code

---

## Implementation Order

```
M1 (models) → M2 (parser) → M3a/b (CSS/JS) → M3c (message renderers) → M3d (assembly) → M4 (CLI) → M5 (smoke test)
```

Each step can be developed and tested independently before moving to the next.

---

## Edge Cases to Handle

| Case | Handling |
|------|----------|
| `messageAnnotations` missing or empty | Default to `[]` |
| `fileContent` missing from annotation | Skip that attachment |
| `<entity>` ref not found in entity map | Replace with `[file]` |
| `text` field is empty string on bot message | Render empty bubble (don't crash) |
| `createdAt` parse fails | Fall back to `datetime.min` |
| `zeroQuery.data` missing | Entity map is empty; all refs → `[file]` |

