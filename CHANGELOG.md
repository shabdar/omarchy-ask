# Changelog

## 1.0.2

Prompts never travel on process argv.

- Overlay, `ask.py`, `open_chat.py`, and `wl-copy` take the question on stdin
- Agent CLIs receive the question via stdin or `--prompt-file /dev/stdin`
- Copilot and OpenCode overlay answers fail closed to Open in browser (those CLIs require the prompt as an argument)
- Chromium is launched at the allowlisted origin; the seeded URL is pasted, not passed on chromium's command line

## 1.0.1

Marketplace-ready identity.

- Plugin id `io.github.shabdar.omask` (the `omarchy.*` namespace is reserved for built-ins)
- Display name `omAsk`
- Docs: install path, IPC, update/remove commands, external dependencies
- Install still does not write Hyprland binds or other user config
- Migration: `omarchy plugin remove omask --yes`, re-add from git, then update the Super+Q bind to toggle `io.github.shabdar.omask`

## 1.0.0

First public release.

- Plugin id `omask` (the `omarchy.*` namespace is reserved for built-ins)
- Centered overlay for a one-shot question to `omarchy default agent`
- Short on-screen answer via that agent's CLI (Grok, Claude, Gemini, Copilot, Codex, OpenCode, Crush, Pi, Oh My Pi)
- Open in browser starts the agent's web chat with `?q=` in a new Chromium window; grok.com Send is confirmed
