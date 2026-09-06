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
  property string askBuf: ""
  property string askErrBuf: ""
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
  readonly property int maxPrompt: 2000
  readonly property int maxAskBytes: 8192
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
    // SVG paths for an allowlisted agent id only.
    var id = AskModel.normalizeAgent(root.provider && root.provider.id ? root.provider.id : "")
    if (!id || !AskModel.PROVIDERS[id]) return []
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

  function stopAsk() {
    // TERM the helper; KILL shortly after if it is still running.
    if (!askProc.running) return
    askProc.signal(15)
    askKill.start()
  }

  function resetQuery() {
    // Clear the prompt, answer, and any in-flight ask process.
    root.promptText = ""
    root.summary = ""
    root.errorText = ""
    root.status = "idle"
    root.askBuf = ""
    root.askErrBuf = ""
    stopAsk()
  }

  function open(payloadJson) {
    // Show the overlay; optional JSON `{ "prompt": "..." }` pre-fills the field.
    var payload = ({})
    try { payload = JSON.parse(AskModel.clip(payloadJson || "{}", 4096)) } catch (e) { payload = ({}) }
    root.refreshProvider()
    root.resetQuery()
    if (payload.prompt) root.promptText = AskModel.clip(payload.prompt, root.maxPrompt)
    root.opened = true
    Qt.callLater(function() {
      promptField.forceActiveFocus()
      promptField.selectAll()
    })
  }

  function close() {
    // Hide the overlay without telling the shell (used by dismiss).
    stopAsk()
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
    // Run ask.py with the current field text on stdin.
    var prompt = AskModel.clip(promptField.text || root.promptText || "", root.maxPrompt)
    if (!prompt || root.asking) return
    root.promptText = prompt
    root.askPrompt = prompt
    root.summary = ""
    root.errorText = ""
    root.askBuf = ""
    root.askErrBuf = ""
    root.status = "asking"
    if (askProc.running) {
      askProc.signal(15)
      askKill.start()
    }
    askProc.running = true
  }

  function fail(message) {
    // Show an error in the overlay body.
    root.status = "error"
    root.errorText = AskModel.clip(message || "Something went wrong.", 240)
  }

  function onAskFinished(raw) {
    // Apply ask.py JSON: answer, open-browser hint, or error.
    var data = AskModel.parseAskOutput(raw)
    if (data.agent) {
      root.agentId = data.agent
      root.provider = AskModel.providerFor(data.agent)
    }
    if (data.ok && data.summary) {
      root.summary = data.summary
      root.errorText = ""
      root.status = "done"
      return
    }
    if (data.code === "open-browser") {
      root.summary = ""
      root.errorText = data.error || "Open the browser to ask this agent."
      root.status = "error"
      return
    }
    root.fail(data.error || "No answer.")
  }

  function copyText(value) {
    // Copy `value` to the Wayland clipboard as its own argv element.
    var text = AskModel.clip(value, 2000)
    if (!text) return
    Quickshell.execDetached(["/usr/bin/wl-copy", "--", text])
  }

  function openBrowser() {
    // Hand off the asked prompt to the agent's web chat, then dismiss.
    var prompt = AskModel.clip(root.askPrompt || root.promptText || promptField.text || "", root.maxPrompt)
    var agent = AskModel.normalizeAgent(root.provider && root.provider.id ? root.provider.id : "")
    var script = root.pluginDir + "/open_chat.py"
    if (prompt) root.copyText(prompt)
    Quickshell.execDetached(["/usr/bin/python3", "-I", "-S", script, "--agent", agent, "--prompt", prompt])
    root.dismiss()
  }

  function refreshAgent() {
    // Re-read the default-agent file through ask.py --info (not FileView.text).
    if (infoProc.running) {
      infoProc.signal(15)
      infoKill.start()
    }
    infoBuf = ""
    infoProc.running = true
  }

  property string infoBuf: ""

  FileView {
    id: agentFile
    path: root.agentFilePath
    preload: false
    blockAllReads: true
    watchChanges: true
    printErrors: false
    onFileChanged: root.refreshAgent()
  }

  Process {
    id: infoProc
    command: ["/usr/bin/python3", "-I", "-S", root.askScript, "--info"]
    stdout: SplitParser {
      splitMarker: ""
      onRead: function(chunk) {
        if (root.infoBuf.length + String(chunk).length > 2048) {
          infoProc.signal(15)
          infoKill.start()
          return
        }
        root.infoBuf += chunk
      }
    }
    onExited: function() {
      var data = AskModel.parseAskOutput(root.infoBuf)
      root.infoBuf = ""
      if (data.agent) root.agentId = data.agent
      root.refreshProvider()
    }
  }

  Process {
    id: askProc
    command: ["/usr/bin/python3", "-I", "-S", root.askScript, "--ask", root.askPrompt]
    stdout: SplitParser {
      splitMarker: ""
      onRead: function(chunk) {
        if (root.askBuf.length + String(chunk).length > root.maxAskBytes) {
          root.stopAsk()
          root.fail("Answer was too large.")
          return
        }
        root.askBuf += chunk
      }
    }
    stderr: SplitParser {
      splitMarker: ""
      onRead: function(chunk) {
        if (root.askErrBuf.length + String(chunk).length > 1024) {
          root.stopAsk()
          return
        }
        root.askErrBuf += chunk
      }
    }
    onExited: function(exitCode) {
      askKill.stop()
      if (!root.opened || root.status !== "asking") return
      if (root.askBuf.replace(/^\s+|\s+$/g, "")) {
        root.onAskFinished(root.askBuf)
        return
      }
      var err = AskModel.clip(root.askErrBuf, 240)
      root.fail(err || ("Ask helper exited " + exitCode + "."))
    }
  }

  Timer {
    id: askKill
    interval: 2000
    repeat: false
    onTriggered: if (askProc.running) askProc.signal(9)
  }

  Timer {
    id: infoKill
    interval: 2000
    repeat: false
    onTriggered: if (infoProc.running) infoProc.signal(9)
  }

  Timer {
    id: askDeadline
    interval: 95000
    repeat: false
    running: root.asking
    onTriggered: {
      root.stopAsk()
      if (root.status === "asking") root.fail("The agent took too long.")
    }
  }

  Component.onCompleted: root.refreshAgent()
  Component.onDestruction: {
    root.stopAsk()
    if (infoProc.running) infoProc.signal(15)
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
              textFormat: Text.PlainText
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
            maximumLength: root.maxPrompt
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            foreground: root.foreground
            accent: Color.accent
            leftPadding: 0
            rightPadding: 0
            topPadding: Style.spacing.xs
            bottomPadding: Style.spacing.xs
            background: Item {}
            onTextChanged: root.promptText = AskModel.clip(text, root.maxPrompt)
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
                textFormat: Text.PlainText
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
