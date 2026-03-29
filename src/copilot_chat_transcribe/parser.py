"""Parse a Microsoft 365 Copilot JSON export into a Conversation."""

import json
import re
import html as html_lib
from datetime import datetime, timezone
from pathlib import Path

from .models import Attachment, Conversation, Message

# Matches <entity type='file' ReferenceId='uuid'>any text</entity>
_ENTITY_RE = re.compile(
    r"<entity[^>]*ReferenceId='([^']*)'[^>]*>(.*?)</entity>",
    re.IGNORECASE | re.DOTALL,
)


def _build_entity_map(store: dict) -> dict[str, str]:
    """Build a referenceId → fileName lookup from the zeroQuery section."""
    entity_map: dict[str, str] = {}
    try:
        items = store["zeroQuery"]["data"]["items"]
        for item in items:
            for entity in item.get("hydratedEntities", []):
                doc = entity.get("document", {})
                ref_id = doc.get("referenceId", "")
                file_info = doc.get("file", {})
                file_name = file_info.get("filename") or file_info.get("fileName", "")
                if ref_id and file_name:
                    entity_map[ref_id] = file_name
    except (KeyError, TypeError):
        pass
    return entity_map


def _resolve_entities(text: str, entity_map: dict[str, str]) -> str:
    """Replace <entity> XML tags with the resolved filename or '[file]'."""
    def replacer(m: re.Match) -> str:
        ref_id = m.group(1)
        return entity_map.get(ref_id, "[file]")

    return _ENTITY_RE.sub(replacer, text)


def _parse_attachment(ann: dict) -> Attachment | None:
    """Convert a raw annotation dict to an Attachment, or None if invalid."""
    meta = ann.get("messageAnnotationMetadata", {})
    data_uri = meta.get("fileContent", "")
    file_name = meta.get("fileName", "attachment")
    file_type = meta.get("fileType", "")
    if not data_uri:
        return None
    return Attachment(file_name=file_name, file_type=file_type, data_uri=data_uri)


def _parse_timestamp(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp string, returning datetime in UTC."""
    try:
        # Python 3.11+ handles +HH:MM offsets natively
        dt = datetime.fromisoformat(raw)
        # Normalise to UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _parse_message(raw: dict, entity_map: dict[str, str]) -> Message | None:
    """Convert a raw message dict to a Message, or None if it should be skipped."""
    author = raw.get("author", "")
    # Drop system / internal messages
    if author == "system" or raw.get("messageType") == "Internal":
        return None
    if author not in ("user", "bot"):
        return None

    text = raw.get("text", "")
    if author == "user":
        text = _resolve_entities(text, entity_map)

    attachments: list[Attachment] = []
    for ann in raw.get("messageAnnotations", []):
        att = _parse_attachment(ann)
        if att is not None:
            attachments.append(att)

    return Message(
        message_id=raw.get("messageId", ""),
        author=author,
        text=text,
        created_at=_parse_timestamp(raw.get("createdAt", "")),
        turn=raw.get("turnCount", 0),
        attachments=attachments,
    )


def parse_file(path: Path) -> Conversation:
    """Load a M365 Copilot JSON export and return a Conversation."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    store = data.get("store", {})
    entity_map = _build_entity_map(store)

    raw_messages = (
        store
        .get("rawConversationResponse", {})
        .get("messages", [])
    )

    messages: list[Message] = []
    for raw in raw_messages:
        msg = _parse_message(raw, entity_map)
        if msg is not None:
            messages.append(msg)

    if not messages:
        raise ValueError("No messages found in the conversation.")

    first_user = next(
        (m for m in messages if m.author == "user"), messages[0]
    )
    title = first_user.text.strip().replace("\r\n", " ").replace("\n", " ")
    if len(title) > 80:
        title = title[:77] + "..."

    return Conversation(
        messages=messages,
        title=title,
        started_at=messages[0].created_at,
        ended_at=messages[-1].created_at,
    )
