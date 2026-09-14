#!/usr/bin/python3
"""Open the default agent's web chat with the overlay question.

Launch /usr/bin/chromium --new-window (not an Omarchy PWA) with an allowlisted
https URL. For grok.com, confirm "Send this message?" with wtype after focus.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounded import MAX_PROMPT_BYTES, read_stdin_prompt, run_bounded

CHAT_URL = {
    "grok": "https://grok.com/?q={q}",
    "claude": "https://claude.ai/new?q={q}",
    "gemini": "https://gemini.google.com/app?q={q}",
    "chatgpt": "https://chatgpt.com/?q={q}",
    "codex": "https://chatgpt.com/?q={q}",
    "copilot": "https://copilot.microsoft.com/?q={q}",
    "opencode": "https://opencode.ai/?q={q}",
    "crush": "https://crush.xyz/?q={q}",
}

CHAT_HOSTS = {
    "grok.com",
    "claude.ai",
    "gemini.google.com",
    "chatgpt.com",
    "copilot.microsoft.com",
    "opencode.ai",
    "crush.xyz",
}

CONFIRM_SEND = {"grok"}
AGENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
ADDR_RE = re.compile(r"^0x[0-9a-f]+$")
HYPRCTL = "/usr/bin/hyprctl"
CHROMIUM = "/usr/bin/chromium"
WL_COPY = "/usr/bin/wl-copy"
WTYPE = "/usr/bin/wtype"
NOTIFY = "/usr/bin/notify-send"


def plain(text: str, limit: int = 160) -> str:
    """Strip markup and controls before notify-send (host AutoText)."""
    cleaned = []
    for ch in str(text or ""):
        o = ord(ch)
        if ch in "<>&" or o < 32 or (0x7F <= o <= 0x9F):
            continue
        cleaned.append(ch)
        if len(cleaned) >= limit:
            break
    return "".join(cleaned)


def notify(title: str, body: str) -> None:
    """Show a short desktop notification if notify-send exists."""
    if not os.path.isfile(NOTIFY):
        return
    try:
        run_bounded(
            [NOTIFY, "-a", "omask", "--", plain(title, 80), plain(body, 160)],
            max_bytes=4096,
            timeout=3,
        )
    except (ValueError, OSError):
        pass


def hypr_json(args: list[str]) -> object:
    """Bounded `hyprctl -j` JSON, or None."""
    try:
        proc = run_bounded([HYPRCTL, *args, "-j"], max_bytes=262144, timeout=2)
    except (ValueError, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def chromium_addresses() -> list[str]:
    """Hyprland addresses of current Chromium windows."""
    clients = hypr_json(["clients"])
    if not isinstance(clients, list):
        return []
    out = []
    for client in clients[:80]:
        if not isinstance(client, dict):
            continue
        if client.get("class") != "chromium":
            continue
        addr = str(client.get("address") or "")
        if ADDR_RE.fullmatch(addr):
            out.append(addr)
    return out


def window_title(addr: str) -> str:
    """Title of the Hyprland client at `addr`."""
    if not ADDR_RE.fullmatch(addr):
        return ""
    clients = hypr_json(["clients"])
    if not isinstance(clients, list):
        return ""
    for client in clients[:80]:
        if isinstance(client, dict) and str(client.get("address") or "") == addr:
            return str(client.get("title") or "")[:200]
    return ""


def focus_address(addr: str) -> bool:
    """Focus `addr` and confirm it is the active window."""
    if not ADDR_RE.fullmatch(addr):
        return False
    try:
        run_bounded(
            [HYPRCTL, "dispatch", f'hl.dsp.focus({{ window = "address:{addr}" }})'],
            max_bytes=4096,
            timeout=2,
        )
    except (ValueError, OSError):
        return False
    active = hypr_json(["activewindow"])
    if not isinstance(active, dict):
        return False
    return str(active.get("address") or "") == addr


def copy_text(text: str) -> None:
    """Put `text` on the Wayland clipboard via stdin (not argv)."""
    if not os.path.isfile(WL_COPY):
        return
    payload = text.encode("utf-8")[:8000]
    try:
        run_bounded([WL_COPY, "--"], max_bytes=4096, timeout=2, stdin_data=payload)
    except (ValueError, OSError):
        pass


def wtype(*args: str) -> None:
    """Type keys into the focused window."""
    if not os.path.isfile(WTYPE):
        return
    try:
        run_bounded([WTYPE, *args], max_bytes=4096, timeout=3)
    except (ValueError, OSError):
        pass


def launch(url: str) -> None:
    """Open `url` in a new Chromium window (not a PWA)."""
    import subprocess
    bin_path = CHROMIUM if os.path.isfile(CHROMIUM) else (shutil.which("chromium") or CHROMIUM)
    subprocess.Popen(
        [bin_path, "--new-window", "--", url],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_new_window(old: list[str], tries: int = 48) -> str:
    """Wait until a Chromium window appears that was not in `old`."""
    old_set = set(old)
    for _ in range(tries):
        time.sleep(0.25)
        for addr in chromium_addresses():
            if addr not in old_set:
                return addr
    return ""


def force_url_in_window(addr: str, url: str, confirm_send: bool) -> None:
    """Re-navigate via the address bar; optionally confirm grok.com Send."""
    copy_text(url)
    if not focus_address(addr):
        return
    time.sleep(0.35)
    if not focus_address(addr):
        return
    wtype("-M", "ctrl", "-k", "l")
    wtype("-m", "ctrl")
    time.sleep(0.15)
    if not focus_address(addr):
        return
    wtype("-M", "ctrl", "-k", "a")
    wtype("-m", "ctrl")
    time.sleep(0.1)
    wtype("-M", "ctrl", "-k", "v")
    wtype("-m", "ctrl")
    time.sleep(0.15)
    wtype("-k", "Return")
    if not confirm_send:
        return
    time.sleep(2.2)
    if not focus_address(addr):
        return
    wtype("-k", "Return")
    time.sleep(0.8)
    title = window_title(addr)
    if title.strip() in ("Grok", "Grok - Chromium") and focus_address(addr):
        wtype("-k", "Return")


def chat_url(agent: str, prompt: str) -> str:
    """Build an allowlisted https chat URL, or ""."""
    if agent not in CHAT_URL or agent in (".", ".."):
        return ""
    template = CHAT_URL[agent]
    q = urllib.parse.quote(prompt[:MAX_PROMPT_BYTES], safe="") if prompt else ""
    url = template.format(q=q) if q else template.split("?")[0]
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return ""
    host = (parsed.hostname or "").lower()
    if host not in CHAT_HOSTS:
        return ""
    if any(ord(c) < 32 for c in url):
        return ""
    return url


def read_prompt() -> str:
    """Read the overlay question from stdin only (NUL- or EOF-terminated)."""
    raw = read_stdin_prompt(MAX_PROMPT_BYTES)
    if not raw:
        return ""
    try:
        return raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return ""


def main(argv: list[str]) -> int:
    """Copy stdin to the clipboard, or open the agent's web chat."""
    parser = argparse.ArgumentParser(description="Open the agent's web chat; prompt on stdin.")
    parser.add_argument("--agent", default="")
    parser.add_argument("--copy", action="store_true", help="Copy stdin to the clipboard and exit.")
    args = parser.parse_args(argv)

    prompt = read_prompt()
    if args.copy:
        if prompt:
            copy_text(prompt)
        return 0

    agent = (args.agent or "").strip().lower()
    if not AGENT_RE.fullmatch(agent) or agent in (".", ".."):
        agent = ""
    url = chat_url(agent, prompt)
    title = agent[:1].upper() + agent[1:] if agent else "omask"
    notify(f"Opening {title}", "Continuing in the browser.")

    if not url:
        notify("omask", f"No web chat URL for {title}.")
        return 0

    origin = urllib.parse.urlunparse(("https", urllib.parse.urlparse(url).netloc, "/", "", "", ""))
    copy_text(url)
    old = chromium_addresses()
    launch(origin)
    addr = wait_new_window(old)
    if not addr:
        return 0
    force_url_in_window(addr, url, confirm_send=agent in CONFIRM_SEND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
