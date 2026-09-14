# Changelog

## 1.0.2

Keep user prompts off process command lines.

- Overlay writes the question to `ask.py --ask` on stdin (`Process.write`)
- `wl-copy` and `open_chat.py` take clipboard/prompt bytes on stdin
- Agent CLIs receive the question via stdin or `--prompt-file /dev/stdin`, not `-p` / positional argv
- Copilot and OpenCode overlay answers fail closed to Open in browser (those CLIs require the prompt as an argument)
- Browser handoff launches the chat host without `?q=` on Chromium argv, then pastes the seeded URL
- Notifications no longer include the question text

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
