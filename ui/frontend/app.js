/**
 * AI Browser Agent - Frontend Application
 * Handles WebSocket communication, UI updates, and user interactions
 */

class BrowserAgentUI {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.isTaskRunning = false;
    this.frameCount = 0;
    this.fpsInterval = null;

    this.elements = {
      statusDot: document.getElementById("statusDot"),
      statusText: document.getElementById("statusText"),
      chatContainer: document.getElementById("chatContainer"),
      taskInput: document.getElementById("taskInput"),
      sendButton: document.getElementById("sendButton"),
      stopButton: document.getElementById("stopButton"),
      browserScreen: document.getElementById("browserScreen"),
      browserPlaceholder: document.getElementById("browserPlaceholder"),
      commandsPanel: document.getElementById("commandsPanel"),
      terminalPanel: document.getElementById("terminalPanel"),
      clearCommands: document.getElementById("clearCommands"),
      clearTerminal: document.getElementById("clearTerminal"),
      fpsCounter: document.getElementById("fpsCounter"),
    };

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.connect();
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
        Math.min(this.elements.taskInput.scrollHeight, 50) + "px";
    });

    // Clear buttons
    this.elements.clearCommands.addEventListener("click", () =>
      this.clearCommands()
    );
    this.elements.clearTerminal.addEventListener("click", () =>
      this.clearTerminal()
    );
  }

  connect() {
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
      this.updateStatus("disconnected", "Disconnected");
      this.elements.sendButton.disabled = true;

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

      case "screenshot":
        this.updateScreenshot(message.data);
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
            <div class="command-reasoning">${this.escapeHtml(
              data.reasoning
            )}</div>
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

  updateScreenshot(dataUrl) {
    this.elements.browserScreen.src = dataUrl;
    this.elements.browserScreen.classList.add("active");
    this.elements.browserPlaceholder.classList.add("hidden");

    // Update FPS counter
    this.frameCount++;
  }

  startFPSCounter() {
    this.fpsInterval = setInterval(() => {
      this.elements.fpsCounter.textContent = `${this.frameCount} FPS`;
      this.frameCount = 0;
    }, 1000);
  }

  clearCommands() {
    this.elements.commandsPanel.innerHTML = `
            <div class="empty-state">
                <p>Commands will appear here</p>
            </div>
        `;
  }

  clearTerminal() {
    this.elements.terminalPanel.innerHTML = `
            <div class="terminal-line info">AI Browser Agent Terminal</div>
            <div class="terminal-line info">Ready...</div>
            <div class="terminal-line">─────────────────────────</div>
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
