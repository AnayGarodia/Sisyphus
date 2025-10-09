/**
 * Sisyphus Agent Application
 * Modern WebSocket-based AI agent interface
 */

class SisyphusAgent {
  constructor() {
    this.ws = null;
    this.connected = false;
    this.taskRunning = false;
    this.frameCount = 0;
    this.activeTab = "terminal";
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;

    this.elements = this.getElements();
    this.init();
  }

  getElements() {
    return {
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
      themeToggle: document.getElementById("themeToggle"),
      sidebar: document.getElementById("sidebar"),
      sidebarToggle: document.getElementById("sidebarToggle"),
    };
  }

  init() {
    console.log("Initializing Sisyphus Agent...");
    this.setupEventListeners();
    this.setupTabs();
    this.setupTheme();
    this.setupSidebar();
    this.setupExampleChips();
    this.connect();
    this.startFPSCounter();
    console.log("Sisyphus Agent initialization complete");
  }

  setupEventListeners() {
    // Send button
    if (this.elements.sendBtn) {
      this.elements.sendBtn.addEventListener("click", () => this.sendTask());
    }

    // Stop button
    if (this.elements.stopBtn) {
      this.elements.stopBtn.addEventListener("click", () => this.stopTask());
    }

    // Enter key handling
    if (this.elements.taskInput) {
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
        this.autoResizeTextarea();
      });
    }

    // Clear button
    if (this.elements.clearBtn) {
      this.elements.clearBtn.addEventListener("click", () => {
        this.activeTab === "terminal"
          ? this.clearTerminal()
          : this.clearCommands();
      });
    }
  }

  setupTheme() {
    if (this.elements.themeToggle) {
      // Load theme from localStorage (safe to use on your own server)
      const savedTheme = localStorage.getItem("theme");
      if (savedTheme === "dark") {
        document.body.classList.add("dark-theme");
      }

      this.elements.themeToggle.addEventListener("click", () => {
        document.body.classList.toggle("dark-theme");
        const theme = document.body.classList.contains("dark-theme")
          ? "dark"
          : "light";
        localStorage.setItem("theme", theme);
      });
    }
  }

  setupSidebar() {
    if (this.elements.sidebarToggle && this.elements.sidebar) {
      // Load sidebar state
      const sidebarCollapsed =
        localStorage.getItem("sidebarCollapsed") === "true";
      if (sidebarCollapsed) {
        this.elements.sidebar.classList.add("collapsed");
      }

      this.elements.sidebarToggle.addEventListener("click", () => {
        this.elements.sidebar.classList.toggle("collapsed");
        const collapsed = this.elements.sidebar.classList.contains("collapsed");
        localStorage.setItem("sidebarCollapsed", collapsed);
      });
    }
  }

  setupExampleChips() {
    const exampleChips = document.querySelectorAll(".example-chip");
    exampleChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        if (this.elements.taskInput) {
          this.elements.taskInput.value = chip.textContent.trim();
          this.elements.taskInput.focus();
          this.autoResizeTextarea();
        }
      });
    });
  }

  autoResizeTextarea() {
    const textarea = this.elements.taskInput;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px";
    }
  }

  setupTabs() {
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const targetTab = button.dataset.tab;

        tabButtons.forEach((btn) => btn.classList.remove("active"));
        tabPanes.forEach((pane) => pane.classList.remove("active"));

        button.classList.add("active");
        const targetPane = document.getElementById(`${targetTab}Tab`);
        if (targetPane) {
          targetPane.classList.add("active");
        }

        this.activeTab = targetTab;
      });
    });
  }

  connect() {
    // Clear any existing reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatus("Connecting...", false);
    this.log("🔄 Connecting to " + wsUrl, "info");
    console.log("Attempting WebSocket connection to:", wsUrl);

    try {
      this.ws = new WebSocket(wsUrl);
      this.setupWebSocketHandlers();
    } catch (error) {
      console.error("WebSocket creation failed:", error);
      this.handleConnectionError(error);
    }
  }

  setupWebSocketHandlers() {
    this.ws.onopen = () => this.handleOpen();
    this.ws.onmessage = (event) => this.handleIncomingMessage(event);
    this.ws.onerror = (error) => this.handleError(error);
    this.ws.onclose = (event) => this.handleClose(event);
  }

  handleOpen() {
    console.log("✅ WebSocket connected");
    this.connected = true;
    this.reconnectAttempts = 0;
    this.updateStatus("Connected", true);
    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = false;
    }
    this.log("✅ Connected to Sisyphus backend", "success");

    // Send initialize message
    this.send({
      type: "initialize",
      config: {},
    });
  }

  handleIncomingMessage(event) {
    try {
      const message = JSON.parse(event.data);
      console.log("Received message:", message.type, message);
      this.handleMessage(message);
    } catch (error) {
      console.error("Message parsing error:", error);
      this.log(`❌ Failed to parse message: ${error.message}`, "error");
    }
  }

  handleError(error) {
    console.error("WebSocket error:", error);
    this.log("❌ WebSocket connection error", "error");
  }

  handleClose(event) {
    console.log(
      "WebSocket disconnected. Code:",
      event.code,
      "Reason:",
      event.reason
    );
    this.connected = false;
    this.updateStatus("Disconnected", false);
    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = true;
    }

    this.hideBrowserDisplay();

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(
        1000 * Math.pow(2, this.reconnectAttempts - 1),
        10000
      );

      this.log(
        `Connection closed (code: ${event.code}). Reconnecting in ${
          delay / 1000
        }s... (Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
        "warning"
      );

      this.reconnectTimeout = setTimeout(() => {
        if (!this.connected) {
          this.connect();
        }
      }, delay);
    } else {
      this.log(
        "❌ Maximum reconnection attempts reached. Please refresh the page.",
        "error"
      );
    }
  }

  handleConnectionError(error) {
    this.updateStatus("Connection Failed", false);
    this.log(
      `❌ Failed to establish connection: ${error.message || error}`,
      "error"
    );
  }

  handleMessage(message) {
    const handlers = {
      status: () => this.handleStatus(message),
      task_start: () => this.onTaskStart(message.task),
      task_end: () => this.onTaskEnd(),
      command: () => this.handleCommand(message),
      terminal: () => this.log(message.content, message.style || "default"),
      frame: () => {
        console.log("📸 Frame received, size:", message.data?.length || 0);
        this.updateFrame(message.data, message.timestamp);
      },
      stream_started: () => this.onStreamStarted(message.fps),
      stream_stopped: () => this.onStreamStopped(),
      error: () => this.handleErrorMessage(message),
      command_history: () => this.handleCommandHistory(message),
    };

    const handler = handlers[message.type];
    if (handler) {
      handler();
    } else {
      console.log("Unknown message type:", message.type, message);
    }
  }

  handleStatus(message) {
    if (message.ready) {
      this.updateStatus(message.message || "Ready", true);
      this.log(message.message || "✅ Agent ready", "success");
    } else {
      this.updateStatus(message.message || "Initializing...", false);
      this.log(message.message || "⏳ Agent initializing...", "info");
    }
  }

  handleCommand(message) {
    this.addCommand(message);
    this.log(`[STEP ${message.step}] ${message.command}`, "command");
    if (message.reasoning) {
      this.log(`  💭 ${message.reasoning}`, "muted");
    }
  }

  handleCommandHistory(message) {
    if (message.commands && Array.isArray(message.commands)) {
      console.log(
        "Command history updated:",
        message.commands.length,
        "commands"
      );
    }
  }

  handleErrorMessage(message) {
    this.log(`❌ ERROR: ${message.message}`, "error");
    this.addChatMessage("error", message.message);
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      console.log("Sent:", message.type);
    } else {
      console.error(
        "Cannot send: WebSocket not connected. State:",
        this.ws?.readyState
      );
      this.log("❌ Cannot send message - not connected", "error");
    }
  }

  updateStatus(text, isConnected) {
    if (this.elements.statusText) {
      this.elements.statusText.textContent = text;
    }
    if (this.elements.statusDot) {
      this.elements.statusDot.classList.toggle("connected", isConnected);
      this.elements.statusDot.classList.toggle(
        "error",
        !isConnected && text.toLowerCase().includes("error")
      );
    }
  }

  updateFrame(dataUrl, timestamp) {
    if (!dataUrl) return;

    // Show the browser section
    const browserSection = document.getElementById("browserSection");
    if (browserSection) {
      browserSection.style.display = "block";
    }

    // Update the image
    if (this.elements.browserDisplay) {
      this.elements.browserDisplay.src = dataUrl;
      this.elements.browserDisplay.style.display = "block";
    }

    // Hide placeholder
    if (this.elements.placeholder) {
      this.elements.placeholder.style.display = "none";
    }

    this.frameCount++;

    if (timestamp && this.elements.latencyBadge) {
      const latency = Date.now() - timestamp * 1000;
      if (latency >= 0 && latency < 5000) {
        this.elements.latencyBadge.textContent = `~${Math.round(latency)}ms`;
      }
    }
  }

  hideBrowserDisplay() {
    if (this.elements.browserDisplay) {
      this.elements.browserDisplay.style.display = "none";
    }
    if (this.elements.placeholder) {
      this.elements.placeholder.style.display = "flex";
    }
    // Don't hide browserSection itself - keep it visible
  }

  onStreamStarted(fps) {
    console.log(`Stream started at ${fps} FPS`);
    this.log(`✅ Browser stream started at ${fps || 10} FPS`, "success");

    // Show browser section
    const browserSection = document.getElementById("browserSection");
    if (browserSection) {
      browserSection.style.display = "block";
    }
  }

  onStreamStopped() {
    console.log("Stream stopped");
    this.hideBrowserDisplay();
    this.log("⏸ Stream stopped", "info");
  }

  startFPSCounter() {
    setInterval(() => {
      if (this.elements.qualityBadge) {
        if (this.frameCount > 0) {
          this.elements.qualityBadge.textContent = `${this.frameCount} FPS`;
          this.frameCount = 0;
        } else {
          this.elements.qualityBadge.textContent = "HD";
        }
      }
    }, 1000);
  }

  sendTask() {
    const task = this.elements.taskInput?.value.trim();
    if (!task || !this.connected || this.taskRunning) {
      console.log("Cannot send task:", {
        task: !!task,
        connected: this.connected,
        taskRunning: this.taskRunning,
      });
      return;
    }

    this.addChatMessage("user", task);
    this.log(`\n▶ Task: ${task}`, "task");

    this.elements.taskInput.value = "";
    this.elements.taskInput.style.height = "auto";

    this.send({
      type: "execute_task",
      task: task,
    });
  }

  stopTask() {
    this.log("⏹ Stopping task...", "warning");
    this.send({
      type: "stop_task",
    });
  }

  onTaskStart(task) {
    this.taskRunning = true;
    if (this.elements.sendBtn) {
      this.elements.sendBtn.style.display = "none";
    }
    if (this.elements.stopBtn) {
      this.elements.stopBtn.style.display = "flex";
    }
    if (this.elements.taskInput) {
      this.elements.taskInput.disabled = true;
    }

    this.addChatMessage("status", "⚙️ Executing task...");
    this.log("▶ Task execution started", "info");
  }

  onTaskEnd() {
    this.taskRunning = false;
    if (this.elements.sendBtn) {
      this.elements.sendBtn.style.display = "flex";
    }
    if (this.elements.stopBtn) {
      this.elements.stopBtn.style.display = "none";
    }
    if (this.elements.taskInput) {
      this.elements.taskInput.disabled = false;
    }

    this.addChatMessage("status", "✅ Task completed");
    this.log("✅ Task completed successfully\n" + "=".repeat(70), "success");
  }

  addChatMessage(type, content) {
    if (!this.elements.chatMessages) return;

    const container = this.elements.chatMessages;
    const welcome = container.querySelector(".welcome-container");
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
    if (!this.elements.commandsPanel) return;

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
    if (!this.elements.terminal) return;

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
      output: "#94a3b8",
      default: "#94a3b8",
    };

    line.style.color = colors[style] || colors.default;

    if (["success", "error", "task"].includes(style)) {
      line.style.fontWeight = "bold";
    }

    this.elements.terminal.appendChild(line);
    this.elements.terminal.scrollTop = this.elements.terminal.scrollHeight;
  }

  clearTerminal() {
    if (this.elements.terminal) {
      this.elements.terminal.innerHTML = `
        <div class="terminal-line">Sisyphus Agent Terminal v1.0</div>
        <div class="terminal-line">Ready to execute tasks...</div>
        <div class="terminal-line terminal-divider">${"=".repeat(70)}</div>
      `;
    }
  }

  clearCommands() {
    if (this.elements.commandsPanel) {
      this.elements.commandsPanel.innerHTML = `
        <div class="empty-state">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 6L2 12L8 18M16 6L22 12L16 18"/>
          </svg>
          <p>Commands will appear here as the agent executes tasks</p>
        </div>
      `;
    }
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize application when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM loaded, initializing Sisyphus Agent...");
  window.sisyphusAgent = new SisyphusAgent();
  console.log("✅ Sisyphus Agent ready");
});
