# Marketplace listing (do not auto-file)

Paste into a new issue on [omacom/omarchy-plugin-marketplace](https://github.com/omacom/omarchy-plugin-marketplace).

**Title:** `[Plugin]: omAsk`

**Repository URL:** `https://github.com/shabdar/omarchy-ask`

**Category:** `Productivity`

**Tags:** `ai`, `quickshell`, `hyprland`

**Maintainer notes:**

> Overlay plugin. Enter runs `/usr/bin/python3 -I -S ask.py --ask` with the question on stdin (not argv), which execs the user’s already-installed default-agent CLI the same way (stdin / `/dev/stdin`, 90s cap, no yolo/allow-all). Open-in-browser launches Chromium at an allowlisted origin only; the seeded URL is pasted via wl-copy stdin + wtype + hyprctl. bash -c is only used to resolve mise-provided agent binaries on PATH. No sudo, no downloads, no writes to user config. Bind is documented; install does not edit bindings.lua. No persistent cache file.
