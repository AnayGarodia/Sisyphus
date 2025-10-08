/**
 * Sisyphus Agent Application
 * Handles WebSocket connection and UI interactions
 */

class SisyphusAgent {
  constructor() {
    this.ws = null;
    this.connected = false;
    this.taskRunning = false;
    this.frameCount = 0;
    this.activeTab = "terminal";

    this.elements = {
      statusDot: document.getElementById("statusDot"),
      statusText: document.getElementById("statusText"),
      taskInput: document.getElementById("taskInput"),
      sendBtn: document.getElementById("sendBtn"),
      stopBtn: document.getElementById("stopBtn"),
      browserDisplay: document.getElementById("browserDisplay"),
      placeholder: document.getElementById("placeholder"),
      terminal: document.getElementById("terminal"),
      chatMessages: document.getElementById("chatMessages"),
      latencyBadge: document.getElementById("latencyBadge"),
      qualityBadge: document.getElementById("qualityBadge"),
      commandsPanel: document.getElementById("commandsPanel"),
      clearBtn: document.getElementById("clearBtn"),
    };

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.setupTabs();
    this.connect();
    this.startFPSCounter();
  }

  setupEventListeners() {
    // Send button
    this.elements.sendBtn.addEventListener("click", () => this.sendTask());

    // Stop button
    this.elements.stopBtn.addEventListener("click", () => this.stopTask());

    // Enter key to send (Shift+Enter for new line)
    this.elements.taskInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!this.elements.sendBtn.disabled) {
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
    this.elements.clearBtn.addEventListener("click", () => {
      if (this.activeTab === "terminal") {
        this.clearTerminal();
      } else {
        this.clearCommands();
      }
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

  connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatus("Connecting...", false);
    this.log("Connecting to WebSocket...", "info");

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("WebSocket connected");
      this.connected = true;
      this.updateStatus("Connected", true);
      this.elements.sendBtn.disabled = false;
      this.log("✓ Connected to Sisyphus backend", "success");

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
        this.log(`ERROR: Failed to parse message - ${error.message}`, "error");
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      this.updateStatus("Connection Error", false);
      this.log("ERROR: WebSocket connection failed", "error");
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
      this.connected = false;
      this.updateStatus("Disconnected", false);
      this.elements.sendBtn.disabled = true;
      this.log("Connection closed. Reconnecting in 3s...", "warning");

      // Hide browser display on disconnect
      this.elements.browserDisplay.style.display = "none";
      this.elements.placeholder.style.display = "block";

      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (!this.connected) {
          console.log("Attempting to reconnect...");
          this.connect();
        }
      }, 3000);
    };
  }

  handleMessage(message) {
    console.log("Received message:", message);

    switch (message.type) {
      case "status":
        if (message.ready) {
          this.updateStatus(message.message || "Ready", true);
          this.log(message.message || "Agent ready", "info");
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
        this.log(`[STEP ${message.step}] ${message.command}`, "command");
        if (message.reasoning) {
          this.log(`  Reasoning: ${message.reasoning}`, "muted");
        }
        break;

      case "terminal":
        this.log(message.content, message.style || "default");
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
        this.log(`ERROR: ${message.message}`, "error");
        this.addChatMessage("error", message.message);
        break;

      default:
        console.log("Unknown message type:", message.type);
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      console.log("Sent message:", message);
    } else {
      console.error("WebSocket is not connected");
      this.log("ERROR: Cannot send message - not connected", "error");
    }
  }

  updateStatus(text, isConnected) {
    this.elements.statusText.textContent = text;
    if (isConnected) {
      this.elements.statusDot.classList.add("connected");
      this.elements.statusDot.classList.remove("error");
    } else {
      this.elements.statusDot.classList.remove("connected");
      if (text.includes("Error")) {
        this.elements.statusDot.classList.add("error");
      }
    }
  }

  updateFrame(dataUrl, timestamp) {
    if (!dataUrl) return;

    this.elements.browserDisplay.src = dataUrl;
    this.elements.browserDisplay.style.display = "block";
    this.elements.placeholder.style.display = "none";

    this.frameCount++;

    // Calculate latency
    if (timestamp) {
      const latency = Date.now() - timestamp * 1000;
      if (latency >= 0 && latency < 5000) {
        this.elements.latencyBadge.textContent = `~${Math.round(latency)}ms`;
      }
    }
  }

  onStreamStarted(fps) {
    console.log(`Stream started at ${fps} FPS`);
    this.log(`✓ Browser stream started at ${fps || 10} FPS`, "success");
  }

  onStreamStopped() {
    console.log("Stream stopped");
    this.elements.browserDisplay.style.display = "none";
    this.elements.placeholder.style.display = "block";
    this.log("Stream stopped", "info");
  }

  startFPSCounter() {
    setInterval(() => {
      if (this.frameCount > 0) {
        this.elements.qualityBadge.textContent = `${this.frameCount} FPS`;
        this.frameCount = 0;
      } else {
        this.elements.qualityBadge.textContent = "HD";
      }
    }, 1000);
  }

  sendTask() {
    const task = this.elements.taskInput.value.trim();
    if (!task || !this.connected || this.taskRunning) return;

    this.addChatMessage("user", task);
    this.log(`\n► Task: ${task}`, "task");

    this.elements.taskInput.value = "";
    this.elements.taskInput.style.height = "auto";

    this.send({
      type: "execute_task",
      task: task,
    });
  }

  stopTask() {
    this.log("Stopping task...", "warning");
    this.send({
      type: "stop_task",
    });
  }

  onTaskStart(task) {
    this.taskRunning = true;
    this.elements.sendBtn.style.display = "none";
    this.elements.stopBtn.style.display = "flex";
    this.elements.taskInput.disabled = true;

    this.addChatMessage("status", "Executing task...");
    this.log("Task execution started", "info");
  }

  onTaskEnd() {
    this.taskRunning = false;
    this.elements.sendBtn.style.display = "flex";
    this.elements.stopBtn.style.display = "none";
    this.elements.taskInput.disabled = false;

    this.addChatMessage("status", "✓ Task completed");
    this.log(
      "✓ Task completed successfully\n────────────────────────────────",
      "success"
    );
  }

  addChatMessage(type, content) {
    const container = this.elements.chatMessages;

    // Remove welcome message on first interaction
    const welcome = container.querySelector(".welcome-message");
    if (welcome) {
      welcome.remove();
    }

    const msg = document.createElement("div");
    msg.className = `chat-message ${type}`;
    msg.textContent = content;

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
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
      ${
        data.reasoning
          ? `<div class="command-reasoning">${this.escapeHtml(
              data.reasoning
            )}</div>`
          : ""
      }
    `;

    this.elements.commandsPanel.appendChild(commandDiv);
    this.elements.commandsPanel.scrollTop =
      this.elements.commandsPanel.scrollHeight;
  }

  log(message, style = "default") {
    const line = document.createElement("div");
    line.className = "terminal-line";
    line.textContent = message;

    const colors = {
      success: "#10b981",
      error: "#ef4444",
      warning: "#f59e0b",
      info: "#3b82f6",
      command: "#34d399",
      task: "#60a5fa",
      muted: "#64748b",
      default: "#cbd5e1",
    };

    line.style.color = colors[style] || colors.default;
    if (style === "success" || style === "error" || style === "task") {
      line.style.fontWeight = "bold";
    }

    this.elements.terminal.appendChild(line);
    this.elements.terminal.scrollTop = this.elements.terminal.scrollHeight;
  }

  clearTerminal() {
    this.elements.terminal.innerHTML = `
      <div class="terminal-line">Sisyphus Agent Terminal v1.0</div>
      <div class="terminal-line">Ready to execute tasks...</div>
      <div class="terminal-line">────────────────────────────────</div>
    `;
  }

  clearCommands() {
    this.elements.commandsPanel.innerHTML = `
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 6L2 12L8 18M16 6L22 12L16 18"/>
        </svg>
        <p>Commands will appear here as the agent executes</p>
      </div>
    `;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

// Helper function for example chips
function fillTask(task) {
  const input = document.getElementById("taskInput");
  input.value = task;
  input.focus();
  input.dispatchEvent(new Event("input"));
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.sisyphusAgent = new SisyphusAgent();
  console.log("Sisyphus Agent initialized");
});
