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

var AGENT_RE = /^[a-z0-9][a-z0-9._-]{0,31}$/
var MAX_FIELD = 2000

function clip(value, limit) {
  // Bound a string for display or IPC; drop C0/C1 controls.
  var text = String(value || "")
  var out = ""
  var max = limit || MAX_FIELD
  for (var i = 0; i < text.length && out.length < max; i++) {
    var code = text.charCodeAt(i)
    if (code < 32 || (code >= 127 && code <= 159)) continue
    out += text.charAt(i)
  }
  return out
}

function normalizeAgent(raw) {
  // Map `omarchy default agent` aliases to a canonical, allowlisted id.
  var id = String(raw || "").replace(/^\s+|\s+$/g, "").toLowerCase()
  if (id === "claude-code") id = "claude"
  else if (id === "gemini-cli") id = "gemini"
  else if (id === "github-copilot") id = "copilot"
  else if (id === "open-code") id = "opencode"
  else if (id === "oh-my-pi") id = "omp"
  if (!id || id === "." || id === ".." || id.indexOf("/") !== -1 || !AGENT_RE.test(id))
    return ""
  return PROVIDERS[id] ? id : ""
}

function providerFor(raw) {
  // Look up display name, web chat URL, and overlay-ask support.
  var id = normalizeAgent(raw)
  var known = PROVIDERS[id]
  if (known) return known
  return { id: "", name: "AI", web: "", canAsk: false }
}

function placeholderFor(provider) {
  // Input placeholder: "Ask Grok", or "Ask AI" if no default agent is set.
  return "Ask " + (provider && provider.name ? provider.name : "AI")
}

function parseAskOutput(raw) {
  // Parse a small JSON object from ask.py; reject oversized or untyped fields.
  var text = clip(raw, 8192)
  if (!text) return { ok: false, error: "No response from ask helper." }

  var start = text.indexOf("{")
  var end = text.lastIndexOf("}")
  if (start === -1 || end === -1 || end <= start)
    return { ok: false, error: clip(text, 240) }

  var data
  try {
    data = JSON.parse(text.slice(start, end + 1))
  } catch (e) {
    return { ok: false, error: "Could not parse helper output." }
  }
  if (!data || typeof data !== "object") return { ok: false, error: "Invalid helper output." }

  return {
    ok: data.ok === true,
    agent: normalizeAgent(data.agent),
    name: clip(data.name, 40),
    web: clip(data.web, 200),
    canAsk: data.canAsk === true,
    summary: clip(data.summary, 720),
    error: clip(data.error, 240),
    code: clip(data.code, 40)
  }
}
