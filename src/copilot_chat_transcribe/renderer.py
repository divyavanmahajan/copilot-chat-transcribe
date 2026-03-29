"""Render a Conversation to a self-contained HTML string."""

import html as html_lib
from datetime import datetime, timezone

import markdown as md_lib

from .models import Attachment, Conversation, Message

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f9f9f9;
  color: #1a1a1a;
  line-height: 1.6;
  padding: 24px 16px 48px;
}

.chat-container {
  max-width: 820px;
  margin: 0 auto;
}

/* Header */
.chat-header {
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e0e0e0;
}
.chat-header h1 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 4px;
}
.chat-header .date-range {
  font-size: 0.85rem;
  color: #666;
}

/* Message row */
.message {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  align-items: flex-end;
  margin-left: auto;
}

.message.bot {
  align-self: flex-start;
  align-items: flex-start;
}

/* Bubble */
.bubble {
  border-radius: 12px;
  padding: 12px 16px;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.message.user .bubble {
  background: #0f6cbd;
  color: #fff;
  border-bottom-right-radius: 3px;
}

.message.bot .bubble {
  background: #fff;
  color: #1a1a1a;
  border: 1px solid #e0e0e0;
  border-bottom-left-radius: 3px;
}

/* Metadata strip */
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 0.78rem;
  color: #888;
}

.message.user .message-meta {
  flex-direction: row-reverse;
}

.role-label {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
}

.message.user .role-label { color: #0f6cbd; }
.message.bot  .role-label { color: #107c10; }

/* Markdown content inside bot bubble */
.bubble h1, .bubble h2, .bubble h3, .bubble h4 {
  margin-top: 16px;
  margin-bottom: 6px;
  font-size: 1rem;
  font-weight: 600;
}
.bubble h1 { font-size: 1.15rem; }
.bubble h2 { font-size: 1.05rem; }

.bubble p  { margin-bottom: 10px; }
.bubble p:last-child { margin-bottom: 0; }

.bubble ul, .bubble ol {
  padding-left: 20px;
  margin-bottom: 10px;
}
.bubble li { margin-bottom: 3px; }

.bubble strong { font-weight: 700; }
.bubble em     { font-style: italic; }

.bubble hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 12px 0;
}

/* Inline code */
.bubble code {
  font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-size: 0.88em;
  background: rgba(0,0,0,0.07);
  padding: 1px 5px;
  border-radius: 4px;
}

/* Code blocks */
.bubble pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  font-size: 0.85em;
}
.bubble pre code {
  background: none;
  padding: 0;
  color: inherit;
}

/* User bubble overrides for inline code */
.message.user .bubble code {
  background: rgba(255,255,255,0.2);
  color: #fff;
}

/* Images */
.bubble img, .attachment img {
  max-width: 100%;
  border-radius: 6px;
  margin-top: 8px;
  display: block;
}
.attachment figcaption {
  font-size: 0.78rem;
  color: #888;
  margin-top: 3px;
}
.attachment { margin-top: 8px; }

/* Conversation wrapper uses flex column */
.conversation {
  display: flex;
  flex-direction: column;
}

/* Responsive */
@media (max-width: 600px) {
  .message { max-width: 96%; }
  .bubble { padding: 10px 12px; }
}
"""

# ---------------------------------------------------------------------------
# JS  — convert ISO timestamps to local time strings
# ---------------------------------------------------------------------------
JS = """
document.querySelectorAll('time[data-timestamp]').forEach(function(el) {
  try {
    el.textContent = new Date(el.dataset.timestamp).toLocaleString(undefined, {
      dateStyle: 'medium', timeStyle: 'short'
    });
  } catch(e) {}
});
"""


# ---------------------------------------------------------------------------
# Markdown renderer (reuse a single instance)
# ---------------------------------------------------------------------------
_MD = md_lib.Markdown(extensions=["fenced_code", "tables"])


def _render_markdown(text: str) -> str:
    """Convert markdown text to an HTML fragment."""
    _MD.reset()
    return _MD.convert(text)


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------
def _iso(dt: datetime) -> str:
    """Return UTC ISO-8601 string suitable for <time datetime>."""
    if dt == datetime.min.replace(tzinfo=timezone.utc):
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _human(dt: datetime) -> str:
    """Human-readable fallback (JS will replace this client-side)."""
    if dt == datetime.min.replace(tzinfo=timezone.utc):
        return ""
    return dt.strftime("%d %b %Y %H:%M UTC")


# ---------------------------------------------------------------------------
# Attachment renderer
# ---------------------------------------------------------------------------
def _render_attachment(att: Attachment) -> str:
    name = html_lib.escape(att.file_name)
    return (
        f'<figure class="attachment">'
        f'<img src="{att.data_uri}" alt="{name}">'
        f'<figcaption>{name}</figcaption>'
        f"</figure>"
    )


# ---------------------------------------------------------------------------
# Message renderers
# ---------------------------------------------------------------------------
def _render_user_message(msg: Message) -> str:
    text_html = html_lib.escape(msg.text).replace("\r\n", "<br>").replace("\n", "<br>")
    attachments_html = "".join(_render_attachment(a) for a in msg.attachments)
    ts = _iso(msg.created_at)
    human = _human(msg.created_at)
    return (
        f'<div class="message user" id="msg-{html_lib.escape(msg.message_id)}">'
        f'<div class="message-meta">'
        f'<span class="role-label">You</span>'
        f'<time data-timestamp="{ts}">{human}</time>'
        f"</div>"
        f'<div class="bubble">{text_html}{attachments_html}</div>'
        f"</div>"
    )


def _render_bot_message(msg: Message) -> str:
    content_html = _render_markdown(msg.text)
    ts = _iso(msg.created_at)
    human = _human(msg.created_at)
    return (
        f'<div class="message bot" id="msg-{html_lib.escape(msg.message_id)}">'
        f'<div class="message-meta">'
        f'<span class="role-label">Copilot</span>'
        f'<time data-timestamp="{ts}">{human}</time>'
        f"</div>"
        f'<div class="bubble">{content_html}</div>'
        f"</div>"
    )


def _render_message(msg: Message) -> str:
    if msg.author == "user":
        return _render_user_message(msg)
    return _render_bot_message(msg)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------
def _render_header(conv: Conversation) -> str:
    title = html_lib.escape(conv.title)
    start = _human(conv.started_at)
    end = _human(conv.ended_at)
    date_range = f"{start} – {end}" if start != end else start
    return (
        f'<header class="chat-header">'
        f"<h1>{title}</h1>"
        f'<div class="date-range">{date_range}</div>'
        f"</header>"
    )


def render_markdown_doc(conv: Conversation) -> str:
    """Render a Conversation to a plain Markdown document (no images)."""
    lines: list[str] = []
    fmt = "%Y-%m-%d %H:%M UTC"
    start = conv.started_at.strftime(fmt) if conv.started_at != datetime.min.replace(tzinfo=timezone.utc) else ""
    end   = conv.ended_at.strftime(fmt)   if conv.ended_at   != datetime.min.replace(tzinfo=timezone.utc) else ""
    date_range = f"{start} – {end}" if start and end and start != end else (start or end)

    lines.append(f"# {conv.title}")
    lines.append(f"\n_{date_range}_\n")
    lines.append("---\n")

    for msg in conv.messages:
        ts = msg.created_at.strftime(fmt) if msg.created_at != datetime.min.replace(tzinfo=timezone.utc) else ""
        if msg.author == "user":
            lines.append(f"## You  _{ts}_\n")
            lines.append(msg.text.strip())
            att_names = [a.file_name for a in msg.attachments]
            if att_names:
                lines.append("\n_Attachments: " + ", ".join(att_names) + "_")
        else:
            lines.append(f"## Copilot  _{ts}_\n")
            lines.append(msg.text.strip())
        lines.append("\n---\n")

    return "\n".join(lines)


def render(conv: Conversation) -> str:
    """Render a Conversation to a complete self-contained HTML document."""
    header_html = _render_header(conv)
    messages_html = "\n".join(_render_message(m) for m in conv.messages)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(conv.title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="chat-container">
    {header_html}
    <div class="conversation">
{messages_html}
    </div>
  </div>
  <script>{JS}</script>
</body>
</html>"""
