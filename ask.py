#!/usr/bin/env python3
"""One-shot overlay answer for omask.

Prints a single JSON object on stdout, then exits.

  ask.py --info           metadata for `omarchy default agent`
  ask.py --ask <prompt>   short answer from that agent's CLI
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SYSTEM_PROMPT = """You are a desktop quick-answer assistant. The user is mid-task and needs a short, clear, useful answer so they can continue.

Rules:
- Answer in 2 to 5 short sentences.
- Be concrete. Prefer exact commands, key names, and next steps when relevant.
- No preamble, no headings, no bullet lists unless a list is the whole answer.
- No follow-up questions.
- If you are unsure, say so in one sentence and give the best next step."""

# Official `omarchy default agent` ids. can_ask means we have a headless CLI.
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

MAX_SUMMARY_CHARS = 720
ASK_TIMEOUT_SEC = 90
AGENT_FILE = Path.home() / ".config/omarchy/defaults/agent"


def emit(payload: dict, exit_code: int = 0) -> None:
    """Write one JSON object to stdout and exit."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(exit_code)


def default_agent() -> str:
    """Return the id in `omarchy default agent`, or "" if unset."""
    try:
        raw = AGENT_FILE.read_text(encoding="utf-8").strip().lower()
    except OSError:
        raw = ""
    return ALIASES.get(raw, raw) if raw else ""


def provider_for(agent: str) -> dict:
    """Return the provider record for an agent id, including unknown ids."""
    known = PROVIDERS.get(agent)
    if known:
        return dict(known)
    return {
        "id": agent,
        "name": agent[:1].upper() + agent[1:] if agent else "AI",
        "web": "",
        "binary": agent,
        "can_ask": False,
    }


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


def split_lines(text: str) -> list[str]:
    """Normalize newlines and split into lines."""
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def tidy_summary(text: str) -> str:
    """Collapse CLI output to a short overlay paragraph."""
    lines = [line.rstrip() for line in split_lines(text)]
    body = "\n".join(lines).strip()
    if body.startswith("```"):
        parts = body.split("```")
        if len(parts) >= 3:
            body = parts[1]
            if "\n" in body:
                first, rest = body.split("\n", 1)
                if first.strip() and " " not in first.strip():
                    body = rest
    body = " ".join(body.split())
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
    """Run a CLI through a login shell so mise-installed binaries are on PATH."""
    return ["bash", "-lc", 'exec "$1" "${@:2}"', "omask", *argv]


def binary_on_path(binary: str) -> bool:
    """True if `binary` is on PATH, including a login-shell PATH."""
    if not binary:
        return False
    if shutil.which(binary):
        return True
    try:
        probe = subprocess.run(
            ["bash", "-lc", "command -v -- " + binary],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0 and bool((probe.stdout or "").strip())


def argv_for(agent: str, prompt: str) -> list[str] | None:
    """Return the headless CLI argv for this agent, or None if unsupported."""
    if agent == "grok":
        return [
            "grok",
            "--output-format", "plain",
            "--permission-mode", "dontAsk",
            "--no-subagents",
            "--no-plan",
            "--disable-web-search",
            "--max-turns", "1",
            "--system-prompt-override", SYSTEM_PROMPT,
            "-p", prompt,
        ]
    if agent == "claude":
        return [
            "claude",
            "-p",
            "--output-format", "text",
            "--permission-mode", "dontAsk",
            "--max-turns", "1",
            "--append-system-prompt", SYSTEM_PROMPT,
            prompt,
        ]
    if agent == "gemini":
        return ["gemini", "--approval-mode", "plan", "-p", wrapped_prompt(prompt)]
    if agent == "copilot":
        return ["copilot", "--allow-all", "-p", wrapped_prompt(prompt)]
    if agent == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", wrapped_prompt(prompt)]
    if agent == "opencode":
        return ["opencode", "run", wrapped_prompt(prompt)]
    if agent == "crush":
        return ["crush", "run", wrapped_prompt(prompt)]
    if agent in ("pi", "omp"):
        return [
            agent,
            "--print",
            "--no-tools",
            "--system-prompt", SYSTEM_PROMPT,
            "--",
            prompt,
        ]
    return None


def looks_like_auth_error(text: str) -> bool:
    """True if CLI output looks like a missing login / API key."""
    lowered = text.lower()
    needles = ("login", "auth", "unauthor", "401", "api key", "not logged", "sign in")
    return any(n in lowered for n in needles)


def run_cli(argv: list[str]) -> subprocess.CompletedProcess:
    """Run the agent CLI, capturing stdout/stderr, with a hard timeout."""
    return subprocess.run(
        login_argv(argv),
        check=False,
        capture_output=True,
        text=True,
        timeout=ASK_TIMEOUT_SEC,
    )


def ask_agent(provider: dict, prompt: str) -> None:
    """Call the default agent's CLI and emit a summary or an error."""
    binary = provider.get("binary") or provider["id"]
    name = provider["name"]
    argv = argv_for(provider["id"], prompt)
    if not argv:
        emit(
            result(
                provider,
                code="open-browser",
                error=f"No overlay backend for {name} yet. Open the browser to continue.",
            )
        )

    if not binary_on_path(binary):
        emit(
            result(
                provider,
                code="missing-cli",
                error=f"{name} CLI is not on PATH. Install it with `omarchy default agent {provider['id']}`, then try again.",
            )
        )

    try:
        proc = run_cli(argv)
    except subprocess.TimeoutExpired:
        emit(result(provider, code="timeout", error=f"{name} took too long. Try a shorter question, or open the browser."))
    except FileNotFoundError:
        emit(result(provider, code="missing-cli", error=f"Could not start a login shell to run {name}."))

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
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
        emit(
            result(
                empty,
                code="no-agent",
                error="Set a default agent with `omarchy default agent <name>`.",
            )
        )

    provider = provider_for(agent)

    if not argv or argv[0] in ("--info", "info"):
        emit(result(provider, ok=True, canAsk=bool(provider.get("can_ask"))))

    if argv[0] != "--ask":
        emit(result(provider, code="usage", error="Usage: ask.py --ask <prompt>"), 2)

    prompt = " ".join(argv[1:]).strip() if len(argv) > 1 else ""
    if not prompt:
        emit(result(provider, code="empty", error="Type a question first."))

    if not provider.get("can_ask"):
        emit(
            result(
                provider,
                code="open-browser",
                error=f"No overlay backend for {provider['name']}. Open the browser to continue.",
            )
        )

    ask_agent(provider, prompt)


if __name__ == "__main__":
    main(sys.argv[1:])
