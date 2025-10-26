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
      chatMessages: document.getElementById("chatMessages"),
      latencyBadge: document.getElementById("latencyBadge"),
      qualityBadge: document.getElementById("qualityBadge"),
      themeToggle: document.getElementById("themeToggle"),
    };
  }

  init() {
    console.log("Initializing Sisyphus Agent...");
    this.setupEventListeners();
    this.setupTheme();
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
  }

  setupTheme() {
    if (this.elements.themeToggle) {
      // Load theme from localStorage
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

  connect() {
    // Clear any existing reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatus("Connecting...", false);
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
    }
  }

  handleError(error) {
    console.error("WebSocket error:", error);
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

      this.addChatMessage(
        "status",
        `Connection closed. Reconnecting in ${delay / 1000}s... (Attempt ${
          this.reconnectAttempts
        }/${this.maxReconnectAttempts})`
      );

      this.reconnectTimeout = setTimeout(() => {
        if (!this.connected) {
          this.connect();
        }
      }, delay);
    } else {
      this.addChatMessage(
        "error",
        "Maximum reconnection attempts reached. Please refresh the page."
      );
    }
  }

  handleConnectionError(error) {
    this.updateStatus("Connection Failed", false);
    this.addChatMessage(
      "error",
      `Failed to establish connection: ${error.message || error}`
    );
  }

  handleMessage(message) {
    const handlers = {
      status: () => this.handleStatus(message),
      task_start: () => this.onTaskStart(message.task),
      task_end: () => this.onTaskEnd(),
      command: () => this.handleCommand(message),
      terminal: () => this.handleTerminal(message),
      frame: () => {
        console.log("📸 Frame received");
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
      this.addChatMessage("agent", message.message || "Agent ready");
    } else {
      this.updateStatus(message.message || "Initializing...", false);
      this.addChatMessage("status", message.message || "Agent initializing...");
    }
  }

  handleCommand(message) {
    this.addChatMessage(
      "agent",
      `**Step ${message.step}:** ${message.command}\n\n*${
        message.reasoning || "Executing command..."
      }*`
    );
  }

  handleTerminal(message) {
    // Display terminal output in chat
    const content = message.content || "";
    if (content.trim()) {
      this.addChatMessage("agent", content);
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
      this.addChatMessage("error", "Cannot send message - not connected");
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
  }

  onStreamStarted(fps) {
    console.log(`Stream started at ${fps} FPS`);
    this.addChatMessage("agent", `Browser stream started at ${fps || 60} FPS`);
  }

  onStreamStopped() {
    console.log("Stream stopped");
    this.hideBrowserDisplay();
    this.addChatMessage("status", "Stream stopped");
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

    // Remove welcome container when first task is sent
    const welcome = this.elements.chatMessages?.querySelector(
      ".welcome-container"
    );
    if (welcome) {
      welcome.remove();
    }

    // Add user message to chat
    this.addChatMessage("user", task);

    this.elements.taskInput.value = "";
    this.elements.taskInput.style.height = "auto";

    this.send({
      type: "execute_task",
      task: task,
    });
  }

  stopTask() {
    this.addChatMessage("status", "Stopping task...");
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
    
    // Handle markdown-style formatting for bold and italic
    const formattedContent = content
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br>");
    
    msg.innerHTML = formattedContent;

    container.appendChild(msg);
    
    // Smooth scroll to bottom
    container.scrollTop = container.scrollHeight;
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