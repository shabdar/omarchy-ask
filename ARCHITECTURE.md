# Architecture

omAsk is a `keepLoaded` Omarchy overlay (plugin id `io.github.shabdar.omask`). The shell summons `Overlay.qml`; that file never talks to an AI API itself. It runs two helpers and paints the result.

```
omarchy-shell shell toggle io.github.shabdar.omask '{}'
        │
        ▼
 Overlay.qml          layer-shell card (WlrLayer.Overlay)
        │
        ├─ FileView  ~/.config/omarchy/defaults/agent
        │              → AskModel.providerFor() → logo + placeholder
        │
        ├─ Enter     Process: python3 ask.py --ask   (prompt on stdin)
        │              → one JSON object on stdout
        │
        └─ Ctrl+Enter / Open in browser
                     execDetached: python3 open_chat.py --agent … --prompt …
```

## Overlay.qml

Entry point from `manifest.json`. `open` / `close` / `toggle` / `dismiss` are the IPC surface the shell calls.

| Piece | Why |
| --- | --- |
| `keepLoaded: true` | Overlay process stays alive so Super+Q is instant. A code change may not apply until `omarchy restart shell`. |
| `pluginDir` | Prefer `manifest.__sourceDir`. Fallback is `~/.config/omarchy/plugins/io.github.shabdar.omask` because `omarchy plugin add` installs by manifest id. |
| `FileView` | Watcher only. Default agent is read by `ask.py --info`, not `FileView.text()`. |
| `Process askProc` | `/usr/bin/python3 -I -S ask.py --ask` with the question on stdin, SplitParser byte cap, and TERM/KILL. |
| `Quickshell.execDetached` | Argv arrays only (`wl-copy --`, `python3 -I -S open_chat.py`). |
| `WlrLayershell.namespace: "omask"` | Layer-shell identity. |
| `askPrompt` | Frozen copy of the submitted question so Open in browser still works after the field is cleared. |

`status` is `idle` → `asking` → `done` | `error`.

## AskModel.js

Shared by QML only (`.pragma library`). Keep `PROVIDERS` in sync with `ask.py`. `canAsk: true` means overlay answers are implemented for that agent.

`parseAskOutput` takes the first `{…}` in stdout so a CLI banner cannot break JSON parse.

## ask.py

One JSON object on stdout, then exit. The CLI is whatever `omarchy default agent` names (`~/.config/omarchy/defaults/agent`).

```json
{
  "ok": false,
  "agent": "grok",
  "name": "Grok",
  "web": "https://grok.com",
  "canAsk": true,
  "summary": "",
  "error": "",
  "code": ""
}
```

| Mode | Behavior |
| --- | --- |
| `--info` (or no args) | Provider metadata. Overlay runs this when the agent file changes. |
| `--ask` | Headless one-shot. The question is on stdin, never argv. |

`invoke_for()` is the per-agent table. The question is passed on stdin (`grok --prompt-file /dev/stdin`, `claude -p`, `gemini -p`, `codex exec`, `crush run`, `pi`/`omp -- /dev/stdin`). Copilot and OpenCode have no stdin prompt mode; those overlay answers fail closed. Each CLI runs through a login shell so mise binaries resolve.

`code` values the overlay cares about: `open-browser`, `auth`, `missing-cli`, `timeout`, `failed`, `empty`, `usage`, `no-agent`.

## open_chat.py

The CLI session and the consumer website do **not** share a conversation id. Handoff is a continuation packet in `?q=` (overlay question + overlay answer), then Send.

Do **not** use `omarchy launch webapp` (`chromium --app=`). That reuses a PWA and often drops `?q=`. Chromium argv is the allowlisted origin only; the seeded URL is pasted.

```
stdin JSON { prompt, answer } → continuation packet
snapshot Chromium addresses
chromium --new-window <origin>
wait for a new Chromium address
focus it
Ctrl+L, Ctrl+V, Return     paste https://…/?q=<packet>
Return                     send / confirm "Send this message?"
```

No persistent cache file. Browser handoff may copy the question to the clipboard.

## Adding an overlay backend

1. Add a branch in `ask.py` `argv_for()` (headless, stdout text).
2. Set `can_ask: True` / `canAsk: true` for that agent in `ask.py` **and** `AskModel.js`.
3. Add `assets/<id>.svg` and optional `assets/<id>-light.svg` for light themes.

## Adding a web chat

Add a `CHAT_URL` template in `open_chat.py`. `{q}` is `urllib.parse.quote` of the continuation packet. Send is confirmed with Return after navigation.

## Theme

The overlay uses `Color.menu` and `Style`. It follows the active Omarchy theme; do not hard-code colors.
