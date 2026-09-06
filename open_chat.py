#!/usr/bin/env python3
"""Open the default agent's web chat with the overlay question.

The overlay CLI session and the consumer website do not share a conversation
id. Launch Chromium --new-window (not an Omarchy PWA), put ?q= in the URL,
and for grok.com confirm "Send this message?" with wtype.

Log: ~/.cache/omarchy/omask/open.log
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

LOG = Path.home() / ".cache/omarchy/omask/open.log"

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

# grok.com prefills ?q= then asks "Send this message?" instead of submitting.
CONFIRM_SEND = {"grok"}


def log(event: str, **fields) -> None:
    """Append one JSON log line for debugging browser handoff."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"event": event, "pid": os.getpid(), **fields}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def notify(title: str, body: str) -> None:
    """Show a short desktop notification if notify-send is available."""
    send = shutil.which("notify-send")
    if not send:
        return
    subprocess.Popen(
        [send, "-a", "omask", title, body[:180]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a short command without raising on non-zero exit."""
    return subprocess.run(cmd, check=False, timeout=kwargs.pop("timeout", 3), **kwargs)


def chromium_bin() -> str:
    """Return the Chromium binary path."""
    return shutil.which("chromium") or "/usr/bin/chromium"


def chromium_addresses() -> list[str]:
    """Hyprland addresses of current Chromium windows."""
    try:
        clients = json.loads(subprocess.check_output(["hyprctl", "clients", "-j"], text=True, timeout=2))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    return [str(c.get("address")) for c in clients if c.get("class") == "chromium" and c.get("address")]


def window_title(addr: str) -> str:
    """Title of the Hyprland client at `addr`."""
    try:
        clients = json.loads(subprocess.check_output(["hyprctl", "clients", "-j"], text=True, timeout=2))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return ""
    for client in clients:
        if str(client.get("address") or "") == addr:
            return str(client.get("title") or "")
    return ""


def focus_address(addr: str) -> bool:
    """Focus the window at `addr`. Return True if it became the active window."""
    run(
        ["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{addr}" }})'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        active = json.loads(subprocess.check_output(["hyprctl", "activewindow", "-j"], text=True, timeout=2))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    return str(active.get("address") or "") == addr


def copy_text(text: str) -> None:
    """Put `text` on the Wayland clipboard."""
    try:
        subprocess.run(["wl-copy"], input=text, text=True, check=False, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def wtype(*args: str) -> None:
    """Type keys into the focused window via wtype."""
    bin_path = shutil.which("wtype")
    if not bin_path:
        log("no-wtype")
        return
    run([bin_path, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch(url: str) -> None:
    """Open `url` in a new Chromium window (not a PWA)."""
    cmd = [chromium_bin(), "--new-window", url]
    log("launch", cmd=cmd, url=url)
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
    # Chromium may reuse an app window and drop ?q=. Paste the URL in the bar.
    copy_text(url)
    if not focus_address(addr):
        log("focus-failed", addr=addr)
        return
    time.sleep(0.35)
    wtype("-M", "ctrl", "-k", "l")
    wtype("-m", "ctrl")
    time.sleep(0.15)
    wtype("-M", "ctrl", "-k", "a")
    wtype("-m", "ctrl")
    time.sleep(0.1)
    wtype("-M", "ctrl", "-k", "v")
    wtype("-m", "ctrl")
    time.sleep(0.15)
    wtype("-k", "Return")
    log("address-bar", addr=addr, title=window_title(addr))
    if not confirm_send:
        return
    time.sleep(2.2)
    if not focus_address(addr):
        return
    wtype("-k", "Return")
    log("send-1", addr=addr, title=window_title(addr))
    time.sleep(0.8)
    title = window_title(addr)
    if title.strip() in ("Grok", "Grok - Chromium"):
        if focus_address(addr):
            wtype("-k", "Return")
            log("send-2", addr=addr, title=title)
    else:
        log("sent", addr=addr, title=title)


def chat_url(agent: str, prompt: str) -> str:
    """Build the web-chat URL, or "" if this agent has no consumer chat."""
    template = CHAT_URL.get(agent)
    if not template:
        return ""
    if not prompt:
        return template.split("?")[0]
    return template.format(q=urllib.parse.quote(prompt, safe=""))


def main(argv: list[str]) -> int:
    """Open the agent's web chat for `--prompt`, then exit."""
    parser = argparse.ArgumentParser(description="Open the agent's web chat with the overlay question.")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--agent", default="")
    args = parser.parse_args(argv)

    prompt = (args.prompt or "").strip()
    agent = (args.agent or "").strip().lower()
    url = chat_url(agent, prompt)
    log("start", agent=agent, prompt=prompt, url=url)
    title = agent[:1].upper() + agent[1:] if agent else "omask"
    notify(f"Opening {title}", prompt or "(empty prompt)")

    if not url:
        log("no-url", agent=agent)
        notify("omask", f"No web chat URL for {title}.")
        return 0

    copy_text(url)
    old = chromium_addresses()
    launch(url)
    addr = wait_new_window(old)
    if not addr:
        log("no-new-window", old=old)
        return 0
    force_url_in_window(addr, url, confirm_send=agent in CONFIRM_SEND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
