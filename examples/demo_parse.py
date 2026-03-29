"""Example: inspect a conversation file using the copilot_chat package."""

import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from copilot_chat_transcribe.parser import parse_file

conv = parse_file(Path("logs/get-single-conversation/5d41e7f4-5156-4a60-819c-c38184df70aa.json"))
fmt = "%Y-%m-%d %H:%M UTC"
print(f"Title:       {conv.title}")
print(f"Started:     {conv.started_at.strftime(fmt)}")
print(f"Ended:       {conv.ended_at.strftime(fmt)}")
user_count = sum(1 for m in conv.messages if m.author == "user")
bot_count  = sum(1 for m in conv.messages if m.author == "bot")
print(f"Messages:    {len(conv.messages)} ({user_count} user, {bot_count} bot)")
total_att = sum(len(m.attachments) for m in conv.messages)
print(f"Attachments: {total_att} image(s) embedded")
print()
for i, m in enumerate(conv.messages, 1):
    preview = m.text[:65].replace('\n', ' ').replace('\r', '')
    print(f"  [{i}] {m.author:4}  turn={m.turn}  {preview}...")
