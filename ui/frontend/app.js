/**
 * AI Browser Agent - Professional Frontend with Live Screenshot Streaming
 * Ultra-reliable WebSocket-based video feed
 */

class BrowserAgentUI {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.isTaskRunning = false;
    this.isStreaming = false;
    this.activeTab = "commands";
    this.frameCount = 0;
    this.lastFrameTime = Date.now();
    this.fpsUpdateInterval = null;
    this.imageElement = null;

    this.elements = {
      statusDot: document.getElementById("statusDot"),
      statusText: document.getElementById("statusText"),
      streamIndicator: document.getElementById("streamIndicator"),
      chatContainer: document.getElementById("chatContainer"),
      taskInput: document.getElementById("taskInput"),
      sendButton: document.getElementById("sendButton"),
      stopButton: document.getElementById("stopButton"),
      browserVideo: document.getElementById("browserVideo"),
      browserPlaceholder: document.getElementById("browserPlaceholder"),
      streamOverlay: document.getElementById("streamOverlay"),
      commandsPanel: document.getElementById("commandsPanel"),
      terminalPanel: document.getElementById("terminalPanel"),
      clearActive: document.getElementById("clearActive"),
      qualityBadge: document.getElementById("qualityBadge"),
      latencyBadge: document.getElementById("latencyBadge"),
    };

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.connect();
    this.setupTabs();
    this.startFPSCounter();
  }

  setupEventListeners() {
    // Send button
    this.elements.sendButton.addEventListener("click", () => this.sendTask());

    // Stop button
    this.elements.stopButton.addEventListener("click", () => this.stopTask());

    // Enter key to send (Shift+Enter for new line)
    this.elements.taskInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!this.elements.sendButton.disabled) {
          this.sendTask();
        }
      }
    });

    // Auto-resize textarea
    this.elements.taskInput.addEventListener("input", () => {
      this.elements.taskInput.style.height = "auto";
      this.elements.taskInput.style.height =
        Math.min(this.elements.taskInput.scrollHeight, 120) + "px";
    });

    // Clear button
    this.elements.clearActive.addEventListener("click", () => {
      if (this.activeTab === "commands") {
        this.clearCommands();
      } else {
        this.clearTerminal();
      }
    });

    // Example chips
    document.querySelectorAll(".example-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const text = chip.textContent.trim();
        this.elements.taskInput.value = text;
        this.elements.taskInput.focus();
        this.elements.taskInput.dispatchEvent(new Event("input"));
      });
    });
  }

  setupTabs() {
    const tabButtons = document.querySelectorAll(".tab-button");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const targetTab = button.dataset.tab;

        // Update active states
        tabButtons.forEach((btn) => btn.classList.remove("active"));
        tabPanes.forEach((pane) => pane.classList.remove("active"));

        button.classList.add("active");
        document.getElementById(`${targetTab}Tab`).classList.add("active");

        this.activeTab = targetTab;
      });
    });
  }

  async connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatus("connecting", "Connecting...");

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("WebSocket connected");
      this.isConnected = true;
      this.updateStatus("connected", "Connected");
      this.elements.sendButton.disabled = false;

      // Initialize agent
      this.send({
        type: "initialize",
        config: {},
      });
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      this.updateStatus("error", "Connection error");
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
      this.isConnected = false;
      this.isStreaming = false;
      this.updateStatus("disconnected", "Disconnected");
      this.elements.sendButton.disabled = true;
      this.elements.streamIndicator.style.display = "none";

      // Clean up image element
      if (this.imageElement) {
        this.imageElement.remove();
        this.imageElement = null;
      }

      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (!this.isConnected) {
          console.log("Attempting to reconnect...");
          this.connect();
        }
      }, 3000);
    };
  }

  handleMessage(message) {
    switch (message.type) {
      case "status":
        if (message.ready) {
          this.updateStatus("connected", message.message || "Ready");
        }
        break;

      case "task_start":
        this.onTaskStart(message.task);
        break;

      case "task_end":
        this.onTaskEnd();
        break;

      case "command":
        this.addCommand(message);
        break;

      case "terminal":
        this.addTerminalOutput(message.content, message.style);
        break;

      case "frame":
        this.updateFrame(message.data, message.timestamp);
        break;

      case "stream_started":
        this.onStreamStarted(message.fps);
        break;

      case "stream_stopped":
        this.onStreamStopped();
        break;

      case "error":
        this.showError(message.message);
        break;
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  updateStatus(status, text) {
    this.elements.statusText.textContent = text;
    this.elements.statusDot.className = "status-dot";

    if (status === "connected") {
      this.elements.statusDot.classList.add("connected");
    } else if (status === "error" || status === "disconnected") {
      this.elements.statusDot.classList.add("error");
    }
  }

  updateFrame(dataUrl, timestamp) {
    if (!this.isStreaming) {
      return;
    }

    // Create or reuse image element for smooth updates
    if (!this.imageElement) {
      this.imageElement = new Image();
      this.imageElement.style.width = "100%";
      this.imageElement.style.height = "100%";
      this.imageElement.style.objectFit = "contain";
      this.imageElement.style.display = "block";

      // Replace video element with image
      const viewport = this.elements.browserVideo.parentElement;
      this.elements.browserVideo.style.display = "none";
      viewport.appendChild(this.imageElement);
    }

    // Update image source
    this.imageElement.src = dataUrl;

    // Update FPS counter
    this.frameCount++;

    // Calculate latency (timestamp is in seconds, convert to ms)
    const latency = Date.now() - timestamp * 1000;
    if (latency >= 0 && latency < 5000) {
      // Only show if reasonable
      this.elements.latencyBadge.textContent = `~${Math.round(latency)}ms`;
    }
  }

  onStreamStarted(fps) {
    console.log(`Stream started at ${fps} FPS`);
    this.isStreaming = true;
    this.elements.streamIndicator.style.display = "flex";
    this.elements.browserPlaceholder.classList.add("hidden");
    this.elements.streamOverlay.style.display = "none";

    this.addTerminalOutput("✓ Live browser feed connected", "success");
  }

  onStreamStopped() {
    console.log("Stream stopped");
    this.isStreaming = false;
    this.elements.streamIndicator.style.display = "none";

    if (this.imageElement) {
      this.imageElement.remove();
      this.imageElement = null;
    }

    this.elements.browserPlaceholder.classList.remove("hidden");
    this.elements.browserVideo.style.display = "block";
  }

  startFPSCounter() {
    this.fpsUpdateInterval = setInterval(() => {
      if (this.isStreaming && this.frameCount > 0) {
        this.elements.qualityBadge.textContent = `${this.frameCount} FPS`;
      } else {
        this.elements.qualityBadge.textContent = "HD";
      }
      this.frameCount = 0;
    }, 1000);
  }

  sendTask() {
    const task = this.elements.taskInput.value.trim();

    if (!task || !this.isConnected || this.isTaskRunning) {
      return;
    }

    // Add user message to chat
    this.addChatMessage("user", task);

    // Clear input
    this.elements.taskInput.value = "";
    this.elements.taskInput.style.height = "auto";

    // Send to backend
    this.send({
      type: "execute_task",
      task: task,
    });
  }

  stopTask() {
    this.send({
      type: "stop_task",
    });
  }

  onTaskStart(task) {
    this.isTaskRunning = true;
    this.elements.sendButton.style.display = "none";
    this.elements.stopButton.style.display = "flex";
    this.elements.taskInput.disabled = true;

    this.addChatMessage("status", "Executing task...");
  }

  onTaskEnd() {
    this.isTaskRunning = false;
    this.elements.sendButton.style.display = "flex";
    this.elements.stopButton.style.display = "none";
    this.elements.taskInput.disabled = false;

    this.addChatMessage("status", "Task completed");
  }

  addChatMessage(type, content) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `chat-message message-${type}`;
    messageDiv.textContent = content;

    this.elements.chatContainer.appendChild(messageDiv);
    this.elements.chatContainer.scrollTop =
      this.elements.chatContainer.scrollHeight;
  }

  addCommand(data) {
    // Remove empty state if present
    const emptyState =
      this.elements.commandsPanel.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    const commandDiv = document.createElement("div");
    commandDiv.className = "command-item";

    commandDiv.innerHTML = `
      <div class="command-step">STEP ${data.step}</div>
      <div class="command-text">${this.escapeHtml(data.command)}</div>
      <div class="command-reasoning">${this.escapeHtml(data.reasoning)}</div>
    `;

    this.elements.commandsPanel.appendChild(commandDiv);
    this.elements.commandsPanel.scrollTop =
      this.elements.commandsPanel.scrollHeight;
  }

  addTerminalOutput(content, style = "default") {
    const line = document.createElement("div");
    line.className = `terminal-line ${style}`;
    line.textContent = content;

    this.elements.terminalPanel.appendChild(line);
    this.elements.terminalPanel.scrollTop =
      this.elements.terminalPanel.scrollHeight;
  }

  clearCommands() {
    this.elements.commandsPanel.innerHTML = `
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M8 6L2 12L8 18M16 6L22 12L16 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <p>Commands will appear here as the agent executes</p>
      </div>
    `;
  }

  clearTerminal() {
    this.elements.terminalPanel.innerHTML = `
      <div class="terminal-line info">AI Browser Agent Terminal v2.0</div>
      <div class="terminal-line info">Ready to execute tasks...</div>
      <div class="terminal-line info">WebSocket streaming enabled for real-time monitoring</div>
      <div class="terminal-line">────────────────────────────────────</div>
    `;
  }

  showError(message) {
    this.addTerminalOutput(`ERROR: ${message}`, "error");
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.app = new BrowserAgentUI();
});
