"""Data model dataclasses for the M365 Copilot chat formatter."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Attachment:
    """An image or file attached to a user message."""
    file_name: str
    file_type: str      # e.g. "png", "jpg"
    data_uri: str       # full data: URI ready for use in <img src>


@dataclass
class Message:
    """A single user or bot turn in the conversation."""
    message_id: str
    author: str         # "user" | "bot"
    text: str           # raw text; markdown for bot, plain for user
    created_at: datetime
    turn: int           # turnCount (1-based)
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class Conversation:
    """The full parsed conversation."""
    messages: list[Message]
    title: str          # first user message, truncated to 80 chars
    started_at: datetime
    ended_at: datetime
