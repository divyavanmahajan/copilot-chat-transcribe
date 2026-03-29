"""CLI entry point: convert a M365 Copilot chat export to a transcript folder."""

import argparse
import json
import re
import shutil
import sys
import webbrowser
from pathlib import Path

from .parser import parse_file
from .renderer import render, render_markdown_doc


# ---------------------------------------------------------------------------
# Output folder helpers
# ---------------------------------------------------------------------------

def _sanitise_folder_name(name: str) -> str:
    """Strip characters invalid in folder names on Windows/Linux."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(". ")
    return name[:80] or "chat"


def _prompt_folder(default: str) -> Path:
    """Ask the user for an output folder, offering a default."""
    try:
        answer = input(f"Output folder [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    name = answer if answer else default
    return Path(_sanitise_folder_name(name))


def write_output_folder(
    folder: Path,
    conversation,
    source_json_path: Path | None = None,
    source_json_data: dict | None = None,
    open_browser: bool = False,
) -> None:
    """Write transcript.html, transcript.md, and conversation.json into folder."""
    folder.mkdir(parents=True, exist_ok=True)

    html_path = folder / "transcript.html"
    md_path   = folder / "transcript.md"
    json_path = folder / "conversation.json"

    print("Rendering HTML …")
    html_path.write_text(render(conversation), encoding="utf-8")
    print(f"  Written: {html_path}")

    print("Rendering Markdown …")
    md_path.write_text(render_markdown_doc(conversation), encoding="utf-8")
    print(f"  Written: {md_path}")

    if source_json_path is not None:
        shutil.copy2(source_json_path, json_path)
        print(f"  Copied:  {json_path}")
    elif source_json_data is not None:
        json_path.write_text(
            json.dumps(source_json_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  Written: {json_path}")

    if open_browser:
        uri = html_path.resolve().as_uri()
        print(f"Opening {uri} …")
        webbrowser.open(uri)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="copilot-chat-transcribe",
        description=(
            "Convert a Microsoft 365 Copilot chat export to a transcript folder "
            "(transcript.html, transcript.md, conversation.json)."
        ),
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        help="Path to a M365 Copilot JSON export file.",
    )
    mode.add_argument(
        "--connect",
        action="store_true",
        help=(
            "Connect to MSEdge via CDP (default port 9222), browse your "
            "conversations interactively, and download the selected one."
        ),
    )

    p.add_argument(
        "--cdp-url",
        default="http://localhost:9222",
        metavar="URL",
        help="Chrome DevTools Protocol URL for the running browser (default: %(default)s).",
    )
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help=(
            "Output folder path. If omitted you will be prompted "
            "(default suggestion: input filename stem or conversation ID)."
        ),
    )
    p.add_argument(
        "--open",
        action="store_true",
        help="Open transcript.html in the default browser after writing.",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    return p


def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("copilot-chat-transcribe")
    except Exception:
        return "0.0.0"


def _run_file_mode(args: argparse.Namespace) -> None:
    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {args.input} …")
    try:
        conversation = parse_file(args.input)
    except (ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    user_turns = sum(1 for m in conversation.messages if m.author == "user")
    bot_turns  = sum(1 for m in conversation.messages if m.author == "bot")
    print(f"  {len(conversation.messages)} messages ({user_turns} user, {bot_turns} bot)")

    default_folder = args.input.stem
    folder = args.output if args.output else _prompt_folder(default_folder)

    write_output_folder(folder, conversation, source_json_path=args.input, open_browser=args.open)
    print(f"\nDone → {folder}/")


def _run_connect_mode(args: argparse.Namespace) -> None:
    from .connector import connect, prompt_select_conversation, download_conversation

    print(f"Connecting to browser at {args.cdp_url} …")
    try:
        pw, browser, page = connect(args.cdp_url)
    except (ConnectionError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        chat = prompt_select_conversation(page)
        conv_id = chat["conversationId"]
        chat_name = chat.get("chatName", conv_id)
        print(f"\nDownloading conversation: {chat_name} …")
        raw_data = download_conversation(page, conv_id)
    finally:
        pw.stop()

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(raw_data, tmp, ensure_ascii=False)
        tmp_path = Path(tmp.name)

    try:
        print("Parsing …")
        try:
            conversation = parse_file(tmp_path)
        except (ValueError, KeyError) as exc:
            print(f"Error parsing conversation: {exc}", file=sys.stderr)
            sys.exit(1)
    finally:
        tmp_path.unlink(missing_ok=True)

    user_turns = sum(1 for m in conversation.messages if m.author == "user")
    bot_turns  = sum(1 for m in conversation.messages if m.author == "bot")
    print(f"  {len(conversation.messages)} messages ({user_turns} user, {bot_turns} bot)")

    default_folder = conv_id
    folder = args.output if args.output else _prompt_folder(default_folder)

    write_output_folder(folder, conversation, source_json_data=raw_data, open_browser=args.open)
    print(f"\nDone → {folder}/")


def main() -> None:
    p = _build_parser()
    args = p.parse_args()

    if args.connect:
        _run_connect_mode(args)
    elif args.input is not None:
        _run_file_mode(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
