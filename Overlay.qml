import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui
import "AskModel.js" as AskModel

// omask overlay. IPC: open / close / toggle / dismiss.
// Enter → ask.py (short on-screen answer). Ctrl+Enter → open_chat.py.
Item {
  id: root

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null

  property bool opened: false
  property string promptText: ""
  property string summary: ""
  property string errorText: ""
  property string status: "idle"
  property string agentId: ""
  property string askPrompt: ""
  property var provider: AskModel.providerFor("")

  property color background: Color.menu.background
  property color foreground: Color.menu.text
  property color border: Color.menu.border
  property var borderSpec: Border.surfaceSpec("menu", "border", border, Math.max(1, Style.space(2)))
  property color scrim: Color.menu.scrim
  readonly property int cornerRadius: Style.cornerRadius
  property string fontFamily: Style.font.menuFamily
  property int contentMargin: Style.spacing.panelPadding
  property int cardWidth: Math.min(Style.space(640), panel.width - Style.gapsOut * 2)
  readonly property int logoSize: Math.max(Style.space(22), Style.font.heading)
  readonly property string pluginDir: (manifest && manifest.__sourceDir)
    ? String(manifest.__sourceDir)
    : (Quickshell.env("HOME") + "/.config/omarchy/plugins/omask")
  readonly property string askScript: pluginDir + "/ask.py"
  readonly property string agentFilePath: Quickshell.env("HOME") + "/.config/omarchy/defaults/agent"
  readonly property bool asking: status === "asking"
  readonly property bool hasAnswer: status === "done" && summary !== ""
  readonly property bool hasError: status === "error" && errorText !== ""
  readonly property bool showBody: hasAnswer || hasError
  readonly property string placeholder: AskModel.placeholderFor(provider)

  function colorChannelLuminance(value) {
    // sRGB channel to linear luminance component.
    var channel = Number(value)
    if (!isFinite(channel)) return 0
    return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)
  }

  function colorLuminance(color) {
    // Relative luminance of a Qt color, used to pick light vs dark logos.
    return 0.2126 * colorChannelLuminance(color.r)
      + 0.7152 * colorChannelLuminance(color.g)
      + 0.0722 * colorChannelLuminance(color.b)
  }

  function logoCandidates() {
    // SVG paths for the default agent, light variant first on light menus.
    var id = root.provider && root.provider.id ? root.provider.id : ""
    if (!id) return []
    var candidates = []
    if (colorLuminance(root.background) >= 0.5)
      candidates.push(Qt.resolvedUrl("assets/" + id + "-light.svg"))
    candidates.push(Qt.resolvedUrl("assets/" + id + ".svg"))
    return candidates
  }

  function refreshProvider() {
    // Reload the provider record and reset the logo fallback index.
    root.provider = AskModel.providerFor(root.agentId)
    logoMark.candidateIndex = 0
  }

  function resetQuery() {
    // Clear the prompt, answer, and any in-flight ask process.
    root.promptText = ""
    root.summary = ""
    root.errorText = ""
    root.status = "idle"
    if (askProc.running) askProc.running = false
  }

  function open(payloadJson) {
    // Show the overlay; optional JSON `{ "prompt": "..." }` pre-fills the field.
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (e) { payload = ({}) }
    root.refreshProvider()
    root.resetQuery()
    if (payload.prompt) root.promptText = String(payload.prompt)
    root.opened = true
    Qt.callLater(function() {
      promptField.forceActiveFocus()
      promptField.selectAll()
    })
  }

  function close() {
    // Hide the overlay without telling the shell (used by dismiss).
    if (askProc.running) askProc.running = false
    root.opened = false
  }

  function dismiss() {
    // Hide the overlay and notify omarchy-shell so IPC state stays in sync.
    root.close()
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "omask")
  }

  function toggle() {
    // IPC toggle: close if open, otherwise open empty.
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function submit() {
    // Run ask.py with the current field text.
    var prompt = String(promptField.text || root.promptText || "").replace(/^\s+|\s+$/g, "")
    if (!prompt || root.asking) return
    root.promptText = prompt
    root.askPrompt = prompt
    root.summary = ""
    root.errorText = ""
    root.status = "asking"
    askProc.running = false
    askProc.running = true
  }

  function fail(message) {
    // Show an error in the overlay body.
    root.status = "error"
    root.errorText = message || "Something went wrong."
  }

  function onAskFinished(raw) {
    // Apply ask.py JSON: answer, open-browser hint, or error.
    var data = AskModel.parseAskOutput(raw)
    if (data.agent) {
      root.agentId = data.agent
      root.provider = AskModel.providerFor(data.agent)
    }
    if (data.ok && data.summary) {
      root.summary = String(data.summary)
      root.errorText = ""
      root.status = "done"
      return
    }
    if (data.code === "open-browser") {
      root.summary = ""
      root.errorText = String(data.error || "Open the browser to ask this agent.")
      root.status = "error"
      return
    }
    root.fail(String(data.error || "No answer."))
  }

  function copyText(value) {
    // Copy `value` to the Wayland clipboard.
    var text = String(value || "")
    if (!text) return
    Quickshell.execDetached(["bash", "-c", "printf %s " + Util.shellQuote(text) + " | wl-copy"])
  }

  function openBrowser() {
    // Hand off the asked prompt to the agent's web chat, then dismiss.
    // argv list to python3 — Util.execArgv never reached this helper from a keepLoaded overlay.
    var prompt = String(root.askPrompt || root.promptText || promptField.text || "").replace(/^\s+|\s+$/g, "")
    var agent = (root.provider && root.provider.id) ? String(root.provider.id) : ""
    var script = root.pluginDir + "/open_chat.py"
    if (prompt) root.copyText(prompt)
    Quickshell.execDetached(["/usr/bin/python3", script, "--agent", agent, "--prompt", prompt])
    root.dismiss()
  }

  FileView {
    id: agentFile
    path: root.agentFilePath
    watchChanges: true
    printErrors: false
    onLoaded: {
      root.agentId = AskModel.normalizeAgent(text())
      root.refreshProvider()
    }
    onLoadFailed: {
      root.agentId = ""
      root.refreshProvider()
    }
    onFileChanged: reload()
  }

  Process {
    id: askProc
    command: ["bash", "-lc", 'exec python3 "$1" --ask "$2"', "omask", root.askScript, root.askPrompt]
    stdout: StdioCollector {
      id: askOut
      waitForEnd: true
    }
    stderr: StdioCollector {
      id: askErr
      waitForEnd: true
    }
    onExited: function(exitCode) {
      if (!root.opened || root.status !== "asking") return
      var out = String(askOut.text || "")
      if (out.replace(/^\s+|\s+$/g, "")) {
        root.onAskFinished(out)
        return
      }
      var err = String(askErr.text || "").replace(/^\s+|\s+$/g, "")
      root.fail(err ? err.slice(0, 240) : ("Ask helper exited " + exitCode + "."))
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omask"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: root.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      width: root.cardWidth
      height: card.contentTopInset + content.implicitHeight + card.contentBottomInset
      radius: root.cornerRadius
      anchors.centerIn: parent
      color: root.background
      borderSpec: root.borderSpec
      padding: root.contentMargin

      MouseArea { anchors.fill: parent; onClicked: {} }

      Column {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: card.contentLeftInset
        anchors.rightMargin: card.contentRightInset
        anchors.topMargin: card.contentTopInset
        spacing: Style.spacing.md

        Item {
          width: parent.width
          height: Math.max(promptField.implicitHeight, root.logoSize)

          Item {
            id: logoMark
            property var candidates: root.logoCandidates()
            property string candidatesKey: candidates.join("\n")
            property int candidateIndex: 0
            onCandidatesKeyChanged: candidateIndex = 0
            width: root.logoSize
            height: root.logoSize
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter

            Image {
              id: logoImage
              anchors.fill: parent
              source: logoMark.candidateIndex < logoMark.candidates.length ? logoMark.candidates[logoMark.candidateIndex] : ""
              sourceSize.width: root.logoSize * 2
              sourceSize.height: root.logoSize * 2
              fillMode: Image.PreserveAspectFit
              onStatusChanged: if (status === Image.Error && logoMark.candidateIndex < logoMark.candidates.length)
                Qt.callLater(function() { logoMark.candidateIndex++ })
            }

            Text {
              anchors.centerIn: parent
              visible: logoImage.status !== Image.Ready
              text: root.provider && root.provider.name ? root.provider.name.charAt(0) : "?"
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.title
              font.bold: true
            }
          }

          TextField {
            id: promptField
            anchors.left: logoMark.right
            anchors.right: trailing.left
            anchors.leftMargin: Style.spacing.lg
            anchors.rightMargin: Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            text: root.promptText
            placeholderText: root.placeholder
            readOnly: root.asking
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            foreground: root.foreground
            accent: Color.accent
            leftPadding: 0
            rightPadding: 0
            topPadding: Style.spacing.xs
            bottomPadding: Style.spacing.xs
            background: Item {}
            onTextChanged: root.promptText = text
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                root.dismiss()
                event.accepted = true
              } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && (event.modifiers & Qt.ControlModifier)) {
                root.openBrowser()
                event.accepted = true
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                root.submit()
                event.accepted = true
              }
            }
          }

          Item {
            id: trailing
            width: trailingInner.implicitWidth
            height: parent.height
            anchors.right: parent.right

            Row {
              id: trailingInner
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(4)
              visible: !root.asking

              Text {
                text: root.hasAnswer || root.hasError ? "Ctrl+Enter browser" : "Enter ask   Esc close"
                color: root.foreground
                opacity: 0.55
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                anchors.verticalCenter: parent.verticalCenter
              }
            }

            Row {
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(5)
              visible: root.asking

              Repeater {
                model: 3
                Rectangle {
                  width: Style.space(6)
                  height: Style.space(6)
                  radius: width / 2
                  color: Color.accent
                  opacity: 0.25
                  SequentialAnimation on opacity {
                    running: root.asking
                    loops: Animation.Infinite
                    PauseAnimation { duration: index * 140 }
                    NumberAnimation { to: 1; duration: 280; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 0.25; duration: 280; easing.type: Easing.InOutQuad }
                    PauseAnimation { duration: (2 - index) * 140 }
                  }
                }
              }
            }
          }
        }

        Column {
          width: parent.width
          visible: root.showBody
          spacing: Style.spacing.md
          leftPadding: root.logoSize + Style.spacing.lg
          rightPadding: 0

          Text {
            width: parent.width - parent.leftPadding
            visible: root.hasAnswer
            text: root.summary
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: root.foreground
            opacity: 0.92
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            lineHeight: 1.35
            maximumLineCount: 8
            elide: Text.ElideRight
          }

          Text {
            width: parent.width - parent.leftPadding
            visible: root.hasError
            text: root.errorText
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            maximumLineCount: 4
            elide: Text.ElideRight
          }

          Row {
            spacing: Style.spacing.sm
            visible: root.showBody

            Button {
              text: "Open in browser"
              enabled: !!(root.provider && root.provider.web)
              active: true
              foreground: root.foreground
              accent: Color.accent
              fontFamily: root.fontFamily
              onClicked: root.openBrowser()
            }

            Button {
              text: "Copy"
              visible: root.hasAnswer
              bordered: true
              foreground: root.foreground
              accent: Color.accent
              fontFamily: root.fontFamily
              onClicked: root.copyText(root.summary)
            }
          }
        }
      }
    }
  }
}
