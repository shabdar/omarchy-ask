# Architecture

omask is a `keepLoaded` Omarchy overlay. The shell summons `Overlay.qml`; that file never talks to an AI API itself. It runs two helpers and paints the result.

```
omarchy-shell shell toggle omask '{}'
        │
        ▼
 Overlay.qml          layer-shell card (WlrLayer.Overlay)
        │
        ├─ FileView  ~/.config/omarchy/defaults/agent
        │              → AskModel.providerFor() → logo + placeholder
        │
        ├─ Enter     Process: python3 ask.py --ask "<prompt>"
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
| `pluginDir` | Prefer `manifest.__sourceDir`. Fallback is `~/.config/omarchy/plugins/omask` because `omarchy plugin add` installs by manifest id. |
| `Process askProc` | `bash -lc 'exec python3 …'` so mise-installed CLIs are on a login PATH. |
| `Quickshell.execDetached(["/usr/bin/python3", …])` | `Util.execArgv` never reached the helper from this keepLoaded overlay. Call python3 with an argv list. |
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
| `--info` (or no args) | Provider metadata only. Overlay uses FileView instead; handy from a terminal. |
| `--ask <prompt>` | Headless one-shot for that agent's CLI. |

`argv_for()` is the per-agent table: `grok -p`, `claude -p`, `gemini -p`, `copilot -p`, `codex exec`, `opencode run`, `crush run`, `pi --print`, `omp --print`. Each runs through a login shell so mise binaries resolve.

`code` values the overlay cares about: `open-browser`, `auth`, `missing-cli`, `timeout`, `failed`, `empty`, `usage`, `no-agent`.

## open_chat.py

The CLI session and the consumer website do **not** share a conversation id. Handoff is: new Chromium window + `?q=`.

Do **not** use `omarchy launch webapp` (`chromium --app=`). That reuses a PWA and often drops `?q=`.

```
copy URL
snapshot Chromium addresses
chromium --new-window <url>
wait for a new Chromium address
focus it
Ctrl+L, Ctrl+V, Return     force the URL (PWA reuse can ignore ?q=)
if grok.com: Return        confirm "Send this message?"
```

Traces go to `~/.cache/omarchy/omask/open.log`.

## Adding an overlay backend

1. Add a branch in `ask.py` `argv_for()` (headless, stdout text).
2. Set `can_ask: True` / `canAsk: true` for that agent in `ask.py` **and** `AskModel.js`.
3. Add `assets/<id>.svg` and optional `assets/<id>-light.svg` for light themes.

## Adding a web chat

Add a `CHAT_URL` template in `open_chat.py`. `{q}` is `urllib.parse.quote` of the overlay prompt. If the site needs a Send confirm, add the agent id to `CONFIRM_SEND`.

## Theme

The overlay uses `Color.menu` and `Style`. It follows the active Omarchy theme; do not hard-code colors.
