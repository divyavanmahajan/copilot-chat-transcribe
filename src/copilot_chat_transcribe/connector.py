"""Connect to a running MSEdge browser via CDP and fetch M365 Copilot conversations."""

import socket
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CDP_URL = "http://localhost:9222"
CHAT_BASE_URL = "https://m365.cloud.microsoft/chat"

# Common MSEdge executable locations on Windows
_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# ---------------------------------------------------------------------------
# Port-check + auto-start helpers
# ---------------------------------------------------------------------------

def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if something is listening on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _find_edge() -> str | None:
    """Return the path to msedge.exe, or None if not found."""
    import shutil
    # Check well-known install paths first
    for candidate in _EDGE_CANDIDATES:
        import os
        if os.path.isfile(candidate):
            return candidate
    # Fall back to PATH
    return shutil.which("msedge") or shutil.which("microsoft-edge")


def _start_edge(port: int) -> subprocess.Popen:
    """Launch MSEdge with remote debugging enabled and return the process."""
    edge_exe = _find_edge()
    if not edge_exe:
        raise FileNotFoundError(
            "MSEdge executable not found. Install Microsoft Edge or add it to PATH."
        )
    cmd = [
        edge_exe,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        CHAT_BASE_URL,
    ]
    print(f"Starting MSEdge: {edge_exe} --remote-debugging-port={port} …")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait up to 10 s for the debug port to appear
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _port_open("localhost", port):
            return proc
        time.sleep(0.4)

    proc.terminate()

    # Port did not open — leftover Edge processes likely absorbed the new launch
    # without applying the --remote-debugging-port flag.
    print(
        f"\nMSEdge started but port {port} did not open within 10 seconds.\n"
        "Microsoft confirms this behavior: leftover Edge processes prevent the\n"
        "--remote-debugging-port flag from being applied.\n"
        "✔ Recommended fix: kill all running Edge processes."
    )
    try:
        answer = input("Kill all running Edge processes and retry? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer in ("", "y", "yes"):
        subprocess.run(
            ["taskkill", "/f", "/im", "msedge.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Edge processes terminated. Retrying …")
        proc2 = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline2 = time.monotonic() + 10
        while time.monotonic() < deadline2:
            if _port_open("localhost", port):
                return proc2
            time.sleep(0.4)
        proc2.terminate()
        raise TimeoutError(
            f"MSEdge still could not open debug port {port} after killing existing processes."
        )

    raise TimeoutError(
        f"MSEdge started but the debug port {port} did not open within 10 seconds."
    )


def _ensure_cdp_available(cdp_url: str) -> None:
    """Check if the CDP port is open; if not, offer to start MSEdge."""
    parsed = urlparse(cdp_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 9222

    if _port_open(host, port):
        return  # Already running

    print(f"\nMSEdge is not listening on port {port}.")
    try:
        answer = input("Start MSEdge with remote debugging now? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer in ("", "y", "yes"):
        _start_edge(port)
        print(f"MSEdge started and debug port {port} is open.")
    else:
        raise ConnectionError(
            f"MSEdge is not running on port {port}. "
            "Start it manually with:\n"
            f'  msedge --remote-debugging-port={port}'
        )


# ---------------------------------------------------------------------------
# Browser connection helpers
# ---------------------------------------------------------------------------

def _get_or_create_page(browser):
    """Return the first existing page on chat.cloud.microsoft, or the first page."""
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "cloud.microsoft" in page.url or "m365" in page.url:
                return page
    # Fall back to first available page
    for ctx in browser.contexts:
        if ctx.pages:
            return ctx.pages[0]
    # Create new page in first context
    return browser.contexts[0].new_page()


def connect(cdp_url: str = CDP_URL):
    """Connect to the running MSEdge browser via CDP.

    If the debug port is not open, the user is offered the choice to start
    MSEdge automatically before the connection is attempted.

    Returns (playwright_instance, browser, page). The caller must close
    playwright when done: ``playwright.stop()``.
    """
    from playwright.sync_api import sync_playwright

    _ensure_cdp_available(cdp_url)

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(cdp_url)
    except Exception as exc:
        pw.stop()
        raise ConnectionError(
            f"Could not connect to MSEdge at {cdp_url}.\n"
            f"Error: {exc}"
        ) from exc
    page = _get_or_create_page(browser)
    return pw, browser, page


# ---------------------------------------------------------------------------
# API interception helpers
# ---------------------------------------------------------------------------

def _intercept_post(page, base_url: str, timeout_ms: int = 30_000) -> dict:
    """Reload the current page and intercept the nav-pane POST to base_url.

    Filters on both URL and request body (must contain "RefreshNavPane") so
    we skip any other POSTs the SPA makes during initialisation.
    """
    target = base_url.rstrip("/")

    def _match(response) -> bool:
        url_base = response.url.split("?")[0].rstrip("/")
        if url_base != target or response.request.method != "POST":
            return False
        post_data = response.request.post_data or ""
        return "RefreshNavPane" in post_data

    with page.expect_response(_match, timeout=timeout_ms) as resp_info:
        page.reload(wait_until="domcontentloaded")

    return resp_info.value.json()


def _intercept_get_conversation(page, conversation_id: str, timeout_ms: int = 30_000) -> dict:
    """Navigate to a conversation URL and intercept the JSON data response.

    The listener is registered *before* navigation so it can capture the XHR
    the SPA fires during boot.  We filter on URL path + GET method + a 200
    status, skipping the initial HTML navigation response by checking that the
    response body starts with '{' (JSON object).
    """
    nav_url = f"{CHAT_BASE_URL}/conversation/{conversation_id}"

    def _match(response) -> bool:
        path = response.url.split("?")[0]
        if f"/conversation/{conversation_id}" not in path:
            return False
        if response.request.method != "GET":
            return False
        if response.status != 200:
            return False
        ct = response.headers.get("content-type", "")
        return "application/json" in ct or "text/plain" in ct

    try:
        with page.expect_response(_match, timeout=timeout_ms) as resp_info:
            page.goto(nav_url, wait_until="domcontentloaded")
        return resp_info.value.json()
    except Exception:
        pass  # fall through to direct fetch below

    # Fallback: issue the fetch directly from inside the browser page so that
    # auth cookies are sent automatically, and add the headers the API expects.
    import json as _json
    script = _json.dumps({
        "url": nav_url,
        "headers": {
            "accept": "application/json",
            "x-route-id": "chat-history",
            "x-host-context": '{"clientPlatform":"web","hostName":"officeweb"}',
            "x-edge-shopping-flag": "1",
        }
    })
    js = f"""
async () => {{
    const cfg = {script};
    cfg.headers["x-session-id"] = crypto.randomUUID();
    const resp = await fetch(cfg.url, {{
        method: "GET",
        credentials: "include",
        headers: cfg.headers,
    }});
    if (!resp.ok) {{
        const t = await resp.text().catch(() => "");
        throw new Error("HTTP " + resp.status + " " + t.slice(0, 300));
    }}
    return resp.json();
}}
"""
    return page.evaluate(js)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_conversations(page, limit: int = 10) -> list[dict]:
    """Navigate to the chat home page and intercept the nav-pane POST.

    The listener is registered *before* navigation begins so it captures
    the RefreshNavPane response that the app fires during its boot sequence.
    A 120-second timeout allows time for the user to sign in if needed.
    """
    target = CHAT_BASE_URL.rstrip("/")

    def _match(response) -> bool:
        url_base = response.url.split("?")[0].rstrip("/")
        if url_base != target or response.request.method != "POST":
            return False
        return "RefreshNavPane" in (response.request.post_data or "")

    print(f"  Navigating to {CHAT_BASE_URL} …")
    print("  (Sign in if prompted — waiting up to 2 minutes for conversation list …)")

    try:
        with page.expect_response(_match, timeout=120_000) as resp_info:
            page.goto(CHAT_BASE_URL, wait_until="domcontentloaded")
        data = resp_info.value.json()
    except Exception as exc:
        raise ValueError(
            f"Could not capture conversation list from browser.\n"
            f"Make sure you are signed in at {CHAT_BASE_URL}.\n"
            f"Detail: {exc}"
        ) from exc

    chats = (
        data.get("store", {})
            .get("conversationPageHistoryList", {})
            .get("chats", [])
    )
    return chats[:limit]


def download_conversation(page, conversation_id: str) -> dict:
    """Navigate to a conversation and intercept its JSON response."""
    print(f"  Navigating to conversation {conversation_id} …")
    try:
        return _intercept_get_conversation(page, conversation_id, timeout_ms=30_000)
    except Exception as exc:
        raise ValueError(
            f"Could not download conversation {conversation_id}.\n"
            f"Detail: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Interactive selection
# ---------------------------------------------------------------------------

def _ms_to_dt(ms: int) -> str:
    """Convert a millisecond epoch timestamp to a human-readable UTC string."""
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError):
        return ""


def prompt_select_conversation(page, page_size: int = 10) -> dict:
    """Interactively list conversations and ask the user to pick one.

    Shows ``page_size`` conversations at a time.  Typing 'm' or 'more' shows
    the next page.  Returns the selected chat dict (conversationId, chatName, …).
    """
    print("\nFetching conversation list …")
    all_chats = list_conversations(page, limit=50)
    if not all_chats:
        raise ValueError("No conversations found.")

    offset = 0
    while True:
        batch = all_chats[offset: offset + page_size]
        end = offset + len(batch)
        has_more = end < len(all_chats)

        print(f"\nConversations {offset + 1}–{end} of {len(all_chats)}:\n")
        for i, chat in enumerate(batch, offset + 1):
            name = chat.get("chatName", "(no name)").replace("\r\n", " ").replace("\n", " ")
            if len(name) > 70:
                name = name[:67] + "..."
            updated = _ms_to_dt(chat.get("updateTimeUtc", 0))
            print(f"  [{i:2}]  {updated}  {name}")

        print()
        if has_more:
            prompt = f"Select [1-{len(all_chats)}], or [m]ore: "
        else:
            prompt = f"Select [1-{len(all_chats)}]: "

        raw = input(prompt).strip().lower()

        if raw in ("m", "more"):
            if has_more:
                offset += page_size
            else:
                print("  No more conversations to show.")
        elif raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(all_chats):
                return all_chats[idx - 1]
            print(f"  Please enter a number between 1 and {len(all_chats)}.")
        else:
            hint = " or 'm' for more" if has_more else ""
            print(f"  Enter a number (1–{len(all_chats)}){hint}.")


def navigate_to_chat(page) -> None:
    """Navigate to the chat home page and ask the user to confirm they are signed in.

    Always navigates to CHAT_BASE_URL so that the subsequent reload in
    list_conversations is guaranteed to trigger the nav-pane POST from the
    correct page — regardless of which URL the browser was on before.
    """
    print(f"Navigating to {CHAT_BASE_URL} …")
    page.goto(CHAT_BASE_URL, wait_until="domcontentloaded")

    print(
        "\nPlease sign in if prompted and wait until the chat page is fully "
        "loaded with your conversation list visible."
    )
    try:
        input("  Press Enter when ready: ")
    except (EOFError, KeyboardInterrupt):
        pass
