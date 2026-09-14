# omAsk

A centered [Omarchy](https://omarchy.org/) overlay for a quick question while you are already doing something else.

Type, read a short on-screen answer from the system default AI, and continue in the browser if you want the full chat.

Created by [Ali Shabdar](https://github.com/shabdar).

**Display name:** omAsk · **Plugin id:** `io.github.shabdar.omask` · **License:** MIT · **Version:** 1.0.3

Third-party plugins cannot use the reserved `omarchy.*` id namespace. The public id is `io.github.shabdar.omask`; the GitHub repo is [`omarchy-ask`](https://github.com/shabdar/omarchy-ask). `omarchy plugin add` installs into `~/.config/omarchy/plugins/io.github.shabdar.omask/` from the manifest id, not the repo name.

![Prompt](screenshots/prompt.png)

![Answer](screenshots/answer.png)

## Install

```bash
omarchy plugin add https://github.com/shabdar/omarchy-ask.git --enable --yes
```

Install does **not** edit `~/.config/hypr/bindings.lua`, `shell.json` keybinds, themes, or any other user config. Add a keybind yourself in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + Q", "omAsk", "omarchy-shell shell toggle io.github.shabdar.omask '{}'")
```

`SUPER+Q` is free on a stock Omarchy bind set. `SUPER+SHIFT+A` is ChatGPT, `SUPER+SHIFT+ALT+A` is the Grok web app, `SUPER+SHIFT+CTRL+A` is the coding-agent picker.

Reload Hyprland after saving (`hyprctl reload`).

```bash
omarchy plugin update io.github.shabdar.omask
omarchy plugin remove io.github.shabdar.omask --yes
```

## Use

| Input | Action |
| --- | --- |
| Super+Q | Open / close |
| Enter | Ask the default agent |
| Ctrl+Enter or **Open in browser** | Continue in that agent's web chat |
| **Copy** | Copy the on-screen answer |
| Escape or click the dimmed desktop | Dismiss |

The logo and backend follow `omarchy default agent` (`~/.config/omarchy/defaults/agent`). Overlay answers run that agent's CLI with the question on stdin (Grok, Claude, Gemini, Codex, Crush, Pi, Oh My Pi). Copilot and OpenCode have no stdin prompt mode; use **Open in browser**. Agents without a consumer web chat still answer in the overlay; **Open in browser** stays disabled.

**Open in browser** starts a *new* web chat (the CLI session is not shared). It seeds one user message with your overlay question and the overlay answer, then confirms Send so the site is already digesting that history. grok.com may show **Send this message?** first.

## How it works

```
Super+Q
  Overlay.qml          layer-shell card, keys, logo
    Enter
      ask.py           default-agent CLI → { ok, summary }
    Open in browser
      open_chat.py     agent web chat with ?q= in a new Chromium window
```

`keepLoaded` is on so the overlay stays in memory and Super+Q is instant. Edits under `~/.config/omarchy/plugins/io.github.shabdar.omask/` hot-reload; if a change does not apply, run `omarchy restart shell`.

| File | Role |
| --- | --- |
| `manifest.json` | Plugin id `io.github.shabdar.omask`, kind `overlay` |
| `Overlay.qml` | UI, IPC, runs the helpers |
| `AskModel.js` | Default-agent map and `ask.py` JSON parse |
| `ask.py` | Short answer from the default agent's CLI |
| `open_chat.py` | Browser handoff |
| `assets/` | Agent marks |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the code map and how to extend it.

## External dependencies

License: MIT (`LICENSE`).

Stock on Omarchy unless noted:

- Omarchy with `omarchy-shell` / Quickshell
- Python 3 (`/usr/bin/python3`)
- A default agent: `omarchy default agent <name>`
- That agent's CLI on `PATH` (mise / `omarchy default agent` installs it)
- Chromium (browser handoff)
- `wl-copy`, `wtype` (browser handoff)
- `hyprctl` (focus the new Chromium window)
- `notify-send` (optional desktop notice on browser handoff)

This is not the coding-agent TUI (`omarchy agent` / Super+Shift+Ctrl+A).

Overlay answers invoke the default agent's CLI in a one-shot, tool-restricted mode (no `--yolo` / `--allow-all` / `dontAsk`). They send the question you typed; they do not send clipboard, window titles, or remote content. Gemini/Copilot/Codex/OpenCode/Crush CLIs cannot be proven tool-free; those calls still run with the most restrictive flags the CLI offers and a 90s deadline.

## Remove

```bash
omarchy plugin remove io.github.shabdar.omask --yes
```

That removes the plugin files and disables it in `shell.json`. It does **not** remove:

- The Super+Q bind in `~/.config/hypr/bindings.lua` (you added that)
- Agent CLIs installed with `omarchy default agent`

omAsk does not write a cache or credential file. Browser handoff may copy the question to the clipboard.

## IPC

```bash
omarchy-shell shell toggle io.github.shabdar.omask '{}'
omarchy-shell shell summon io.github.shabdar.omask '{}'
omarchy-shell shell hide io.github.shabdar.omask
omarchy-shell shell summon io.github.shabdar.omask '{"prompt":"Why is my bind not firing?"}'
```

## License

MIT. Copyright (c) 2026 Ali Shabdar.
