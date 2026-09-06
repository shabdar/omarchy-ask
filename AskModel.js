.pragma library

// Default-agent map shared with the overlay. Keep in sync with ask.py.

var PROVIDERS = {
  grok: { id: "grok", name: "Grok", web: "https://grok.com", canAsk: true },
  claude: { id: "claude", name: "Claude", web: "https://claude.ai/new", canAsk: true },
  gemini: { id: "gemini", name: "Gemini", web: "https://gemini.google.com/app", canAsk: true },
  copilot: { id: "copilot", name: "Copilot", web: "https://copilot.microsoft.com", canAsk: true },
  codex: { id: "codex", name: "Codex", web: "https://chatgpt.com", canAsk: true },
  opencode: { id: "opencode", name: "OpenCode", web: "https://opencode.ai", canAsk: true },
  crush: { id: "crush", name: "Crush", web: "https://crush.xyz", canAsk: true },
  pi: { id: "pi", name: "Pi", web: "", canAsk: true },
  omp: { id: "omp", name: "Oh My Pi", web: "", canAsk: true }
}

function normalizeAgent(raw) {
  // Map `omarchy default agent` aliases to the canonical provider id.
  var id = String(raw || "").replace(/^\s+|\s+$/g, "").toLowerCase()
  if (!id) return ""
  if (id === "claude-code") return "claude"
  if (id === "gemini-cli") return "gemini"
  if (id === "github-copilot") return "copilot"
  if (id === "open-code") return "opencode"
  if (id === "oh-my-pi") return "omp"
  return id
}

function providerFor(raw) {
  // Look up display name, web chat URL, and overlay-ask support.
  var id = normalizeAgent(raw)
  var known = PROVIDERS[id]
  if (known) return known
  if (!id) return { id: "", name: "AI", web: "", canAsk: false }
  return { id: id, name: id.charAt(0).toUpperCase() + id.slice(1), web: "", canAsk: false }
}

function placeholderFor(provider) {
  // Input placeholder: "Ask Grok", or "Ask AI" if no default agent is set.
  return "Ask " + (provider && provider.name ? provider.name : "AI")
}

function parseAskOutput(raw) {
  // Parse the first JSON object in ask.py stdout, ignoring CLI banners.
  var text = String(raw || "").replace(/^\s+|\s+$/g, "")
  if (!text) return { ok: false, error: "No response from ask helper." }

  var start = text.indexOf("{")
  var end = text.lastIndexOf("}")
  if (start === -1 || end === -1 || end <= start)
    return { ok: false, error: text.slice(0, 240) }

  try {
    var data = JSON.parse(text.slice(start, end + 1))
    if (!data || typeof data !== "object") return { ok: false, error: "Invalid helper output." }
    return data
  } catch (e) {
    return { ok: false, error: "Could not parse helper output." }
  }
}
