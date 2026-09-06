#!/usr/bin/python3
"""One-shot overlay answer for omask.

Prints a single JSON object on stdout (capped), then exits.

  ask.py --info                 metadata for `omarchy default agent`
  ask.py --ask                  short answer; prompt on stdin
  ask.py --ask <prompt>         same, prompt from argv (capped)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounded import MAX_CHILD_BYTES, read_nofollow, run_bounded

SYSTEM_PROMPT = """You are a desktop quick-answer assistant. The user is mid-task and needs a short, clear, useful answer so they can continue.

Rules:
- Answer in 2 to 5 short sentences.
- Be concrete. Prefer exact commands, key names, and next steps when relevant.
- No preamble, no headings, no bullet lists unless a list is the whole answer.
- No follow-up questions.
- If you are unsure, say so in one sentence and give the best next step."""

PROVIDERS = {
    "grok": {"id": "grok", "name": "Grok", "web": "https://grok.com", "binary": "grok", "can_ask": True},
    "claude": {"id": "claude", "name": "Claude", "web": "https://claude.ai/new", "binary": "claude", "can_ask": True},
    "gemini": {"id": "gemini", "name": "Gemini", "web": "https://gemini.google.com/app", "binary": "gemini", "can_ask": True},
    "copilot": {"id": "copilot", "name": "Copilot", "web": "https://copilot.microsoft.com", "binary": "copilot", "can_ask": True},
    "codex": {"id": "codex", "name": "Codex", "web": "https://chatgpt.com", "binary": "codex", "can_ask": True},
    "opencode": {"id": "opencode", "name": "OpenCode", "web": "https://opencode.ai", "binary": "opencode", "can_ask": True},
    "crush": {"id": "crush", "name": "Crush", "web": "https://crush.xyz", "binary": "crush", "can_ask": True},
    "pi": {"id": "pi", "name": "Pi", "web": "", "binary": "pi", "can_ask": True},
    "omp": {"id": "omp", "name": "Oh My Pi", "web": "", "binary": "omp", "can_ask": True},
}

ALIASES = {
    "claude-code": "claude",
    "gemini-cli": "gemini",
    "github-copilot": "copilot",
    "open-code": "opencode",
    "oh-my-pi": "omp",
}

AGENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
MAX_SUMMARY_CHARS = 720
MAX_PROMPT_BYTES = 4000
ASK_TIMEOUT_SEC = 90
AGENT_FILE = os.path.expanduser("~/.config/omarchy/defaults/agent")
BASH = ["/usr/bin/bash", "--noprofile", "--norc"]


def emit(payload: dict, exit_code: int = 0) -> None:
    """Write one JSON object to stdout and exit."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(exit_code)


def canonical_agent(raw: str) -> str:
    """Allowlist an agent id; reject traversal and shell metacharacters."""
    ident = (raw or "").strip().lower()
    ident = ALIASES.get(ident, ident)
    if not ident or ident in (".", "..") or "/" in ident or "\\" in ident:
        return ""
    if not AGENT_RE.fullmatch(ident):
        return ""
    return ident


def default_agent() -> str:
    """Read `omarchy default agent` through a nofollow descriptor."""
    try:
        raw = read_nofollow(AGENT_FILE, max_bytes=256)
    except PermissionError:
        return ""
    if raw is None:
        return ""
    try:
        text = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return ""
    return canonical_agent(text.split()[0] if text else "")


def provider_for(agent: str) -> dict:
    """Return the provider record for a canonical agent id."""
    known = PROVIDERS.get(agent)
    if known:
        return dict(known)
    return {"id": agent, "name": "AI", "web": "", "binary": "", "can_ask": False}


def result(provider: dict, **extra) -> dict:
    """Build the JSON payload the overlay parses."""
    payload = {
        "ok": False,
        "agent": provider["id"],
        "name": provider["name"],
        "web": provider["web"],
        "canAsk": bool(provider.get("can_ask")),
        "summary": "",
        "error": "",
        "code": "",
    }
    payload.update(extra)
    return payload


def tidy_summary(text: str) -> str:
    """Collapse CLI output to a short overlay paragraph."""
    body = " ".join(str(text or "").replace("\r", "\n").split())
    if body.startswith("```"):
        parts = body.split("```")
        if len(parts) >= 3:
            body = parts[1]
            if " " in body:
                first, rest = body.split(" ", 1)
                if first.isalpha():
                    body = rest
    if len(body) <= MAX_SUMMARY_CHARS:
        return body
    clipped = body[: MAX_SUMMARY_CHARS + 1]
    period = clipped.rfind(". ")
    if period >= 160:
        return clipped[: period + 1].strip()
    return clipped[:MAX_SUMMARY_CHARS].rstrip() + "…"


def wrapped_prompt(prompt: str) -> str:
    """Prefix the user question with the short-answer instructions."""
    return SYSTEM_PROMPT + "\n\nQuestion: " + prompt


def login_argv(argv: list[str]) -> list[str]:
    """Run an allowlisted CLI via a constant bash -c; data stays in argv."""
    return [*BASH, "-c", 'exec "$1" "${@:2}"', "omask", *argv]


def binary_on_path(binary: str) -> bool:
    """True if the allowlisted binary name resolves on PATH."""
    if not binary or not AGENT_RE.fullmatch(binary):
        return False
    try:
        proc = run_bounded([*BASH, "-c", 'command -v -- "$1"', "omask", binary], max_bytes=4096, timeout=8)
    except (ValueError, OSError):
        return False
    return proc.returncode == 0 and bool((proc.stdout or b"").strip())


def argv_for(agent: str, prompt: str) -> list[str] | None:
    """Headless, tool-restricted argv. None if this agent has no overlay backend."""
    if agent == "grok":
        return [
            "grok",
            "--output-format", "plain",
            "--permission-mode", "plan",
            "--no-subagents",
            "--no-plan",
            "--disable-web-search",
            "--max-turns", "1",
            "--tools", "",
            "--system-prompt-override", SYSTEM_PROMPT,
            "-p", prompt,
        ]
    if agent == "claude":
        return [
            "claude",
            "-p",
            "--output-format", "text",
            "--max-turns", "1",
            "--tools", "",
            "--append-system-prompt", SYSTEM_PROMPT,
            "--",
            prompt,
        ]
    if agent == "gemini":
        return ["gemini", "--approval-mode", "plan", "-p", wrapped_prompt(prompt)]
    if agent == "copilot":
        return ["copilot", "-p", wrapped_prompt(prompt)]
    if agent == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "--", wrapped_prompt(prompt)]
    if agent == "opencode":
        return ["opencode", "run", "--", wrapped_prompt(prompt)]
    if agent == "crush":
        return ["crush", "run", "--", wrapped_prompt(prompt)]
    if agent in ("pi", "omp"):
        return [agent, "--print", "--no-tools", "--system-prompt", SYSTEM_PROMPT, "--", prompt]
    return None


def looks_like_auth_error(text: str) -> bool:
    """True if CLI output looks like a missing login / API key."""
    lowered = text.lower()
    return any(n in lowered for n in ("login", "auth", "unauthor", "401", "api key", "not logged", "sign in"))


def read_prompt(argv: list[str]) -> str:
    """Take the ask prompt from remaining argv or from stdin, capped."""
    if argv:
        raw = " ".join(argv).encode("utf-8")
    else:
        raw = sys.stdin.buffer.read(MAX_PROMPT_BYTES + 1)
    if len(raw) > MAX_PROMPT_BYTES:
        return ""
    try:
        text = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return ""
    return text[:MAX_PROMPT_BYTES]


def ask_agent(provider: dict, prompt: str) -> None:
    """Call the default agent's CLI and emit a summary or an error."""
    binary = provider.get("binary") or ""
    name = provider["name"]
    argv = argv_for(provider["id"], prompt)
    if not argv:
        emit(result(provider, code="open-browser", error=f"No overlay backend for {name}. Open the browser to continue."))
    if not binary_on_path(binary):
        emit(result(
            provider,
            code="missing-cli",
            error=f"{name} CLI is not on PATH. Install it with `omarchy default agent {provider['id']}`, then try again.",
        ))
    try:
        proc = run_bounded(login_argv(argv), max_bytes=MAX_CHILD_BYTES, timeout=ASK_TIMEOUT_SEC)
    except ValueError:
        emit(result(provider, code="failed", error=f"{name} returned too much output."))
    except OSError:
        emit(result(provider, code="missing-cli", error=f"Could not start {name}."))

    stdout = (proc.stdout or b"").decode("utf-8", "replace").strip()
    stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
    combined = "\n".join(part for part in (stdout, stderr) if part)

    if proc.returncode != 0 or not stdout:
        if looks_like_auth_error(combined):
            emit(result(provider, code="auth", error=f"Sign in to {name}, then try again."))
        detail = stdout or stderr or f"{name} exited {proc.returncode}."
        emit(result(provider, code="failed", error=tidy_summary(detail) or f"{name} did not return an answer."))

    summary = tidy_summary(stdout)
    if not summary:
        emit(result(provider, code="failed", error=f"{name} returned an empty answer."))
    emit(result(provider, ok=True, summary=summary))


def main(argv: list[str]) -> None:
    """Dispatch `--info` or `--ask` for the system default agent."""
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    agent = default_agent()
    if not agent:
        empty = {"id": "", "name": "AI", "web": "", "binary": "", "can_ask": False}
        emit(result(empty, code="no-agent", error="Set a default agent with `omarchy default agent <name>`."))

    provider = provider_for(agent)
    if provider["id"] not in PROVIDERS:
        emit(result(provider, code="no-agent", error="Unknown default agent. Set one with `omarchy default agent <name>`."))

    if not argv or argv[0] in ("--info", "info"):
        emit(result(provider, ok=True, canAsk=bool(provider.get("can_ask"))))

    if argv[0] != "--ask":
        emit(result(provider, code="usage", error="Usage: ask.py --ask <prompt>"), 2)

    prompt = read_prompt(argv[1:])
    if not prompt:
        emit(result(provider, code="empty", error="Type a question first."))

    if not provider.get("can_ask"):
        emit(result(provider, code="open-browser", error=f"No overlay backend for {provider['name']}. Open the browser to continue."))

    ask_agent(provider, prompt)


if __name__ == "__main__":
    main(sys.argv[1:])
