/**
 * ============================================
 * Sisyphus Agent Application
 * Professional WebSocket-based AI agent interface
 * FIXED: Immediate stop button response
 * ============================================
 */

class SisyphusAgent {
  constructor() {
    // WebSocket connection
    this.ws = null;
    this.connected = false;
    this.taskRunning = false;

    // Performance tracking
    this.frameCount = 0;
    this.lastFrameTime = Date.now();

    // Reconnection handling
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;

    // DOM elements cache
    this.elements = this.getElements();

    // Initialize application
    this.init();
  }

  /**
   * Cache all DOM elements for better performance
   */
  getElements() {
    return {
      // Header elements
      statusDot: document.getElementById("statusDot"),
      statusText: document.getElementById("statusText"),
      themeToggle: document.getElementById("themeToggle"),
      sidebarToggle: document.getElementById("sidebarToggle"),

      // Sidebar elements
      sidebar: document.getElementById("sidebar"),
      terminal: document.getElementById("terminal"),
      commandsList: document.getElementById("commandsList"),
      clearTerminal: document.getElementById("clearTerminal"),
      clearCommands: document.getElementById("clearCommands"),

      // Tab elements
      tabButtons: document.querySelectorAll(".tab-button"),

      // Viewport elements
      viewport: document.getElementById("viewport"),
      browserFrame: document.getElementById("browserFrame"),
      viewportPlaceholder: document.getElementById("viewportPlaceholder"),
      fpsCounter: document.getElementById("fpsCounter"),
      latencyCounter: document.getElementById("latencyCounter"),

      // Chat elements
      chatForm: document.getElementById("chatForm"),
      chatInput: document.getElementById("chatInput"),
      sendButton: document.getElementById("sendButton"),
      stopButton: document.getElementById("stopButton"),
    };
  }

  /**
   * Initialize the application
   */
  init() {
    console.log("🚀 Initializing Sisyphus Agent...");

    this.setupEventListeners();
    this.setupTheme();
    this.setupKeyboardShortcuts();
    this.connect();
    this.startPerformanceMonitoring();

    console.log("✅ Sisyphus Agent initialized successfully");
  }

  /**
   * Setup all event listeners
   */
  setupEventListeners() {
    // Theme toggle
    this.elements.themeToggle?.addEventListener("click", () =>
      this.toggleTheme()
    );

    // Sidebar toggle
    this.elements.sidebarToggle?.addEventListener("click", () =>
      this.toggleSidebar()
    );

    // Tab switching
    this.elements.tabButtons.forEach((button) => {
      button.addEventListener("click", () =>
        this.switchTab(button.dataset.tab)
      );
    });

    // Clear buttons
    this.elements.clearTerminal?.addEventListener("click", () =>
      this.clearTerminal()
    );
    this.elements.clearCommands?.addEventListener("click", () =>
      this.clearCommands()
    );

    // Form submission
    this.elements.chatForm?.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!this.elements.sendButton.disabled) {
        this.sendMessage();
      }
    });

    // Stop button - FIXED: Use capture phase for immediate response
    this.elements.stopButton?.addEventListener(
      "click",
      (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log("🛑🛑🛑 STOP BUTTON CLICKED - SENDING IMMEDIATELY");
        this.stopTask();
      },
      true
    ); // Use capture phase!

    // Chat input handling
    this.elements.chatInput?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!this.elements.sendButton.disabled) {
          this.sendMessage();
        }
      }
    });

    this.elements.chatInput?.addEventListener("input", () =>
      this.handleInputChange()
    );

    // Window resize handler
    window.addEventListener(
      "resize",
      this.debounce(() => this.handleResize(), 250)
    );

    // Visibility change handler
    document.addEventListener("visibilitychange", () =>
      this.handleVisibilityChange()
    );
  }

  /**
   * Setup keyboard shortcuts
   */
  setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      // Ctrl/Cmd + B: Toggle sidebar
      if ((e.ctrlKey || e.metaKey) && e.key === "b") {
        e.preventDefault();
        this.toggleSidebar();
      }

      // Ctrl/Cmd + Shift + L: Toggle theme
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "L") {
        e.preventDefault();
        this.toggleTheme();
      }

      // Escape: Stop task
      if (e.key === "Escape" && this.taskRunning) {
        e.preventDefault();
        console.log("🛑 ESC pressed - stopping task");
        this.stopTask();
      }

      // Ctrl/Cmd + K: Focus input
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        this.elements.chatInput?.focus();
      }
    });
  }

  /**
   * Setup theme from localStorage
   */
  setupTheme() {
    const savedTheme = localStorage.getItem("sisyphus-theme");
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;

    if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
      document.body.classList.add("dark-theme");
    }

    this.updateThemeIcon();
    this.updateMetaThemeColor();
  }

  /**
   * Toggle theme
   */
  toggleTheme() {
    document.body.classList.toggle("dark-theme");
    const theme = document.body.classList.contains("dark-theme")
      ? "dark"
      : "light";
    localStorage.setItem("sisyphus-theme", theme);
    this.updateThemeIcon();
    this.updateMetaThemeColor();
  }

  /**
   * Update theme icon
   */
  updateThemeIcon() {
    const sunIcon = document.querySelector(".sun-icon");
    const moonIcon = document.querySelector(".moon-icon");
    const isDark = document.body.classList.contains("dark-theme");

    if (sunIcon && moonIcon) {
      sunIcon.style.display = isDark ? "none" : "block";
      moonIcon.style.display = isDark ? "block" : "none";
    }
  }

  /**
   * Update meta theme color for mobile browsers
   */
  updateMetaThemeColor() {
    const isDark = document.body.classList.contains("dark-theme");
    const metaTheme = document.querySelector('meta[name="theme-color"]');

    if (metaTheme) {
      metaTheme.setAttribute("content", isDark ? "#000000" : "#ffffff");
    }
  }

  /**
   * Toggle sidebar
   */
  toggleSidebar() {
    const isCurrentlyCollapsed =
      this.elements.sidebar?.classList.contains("collapsed");
    this.elements.sidebar?.classList.toggle("collapsed");

    // Update icons based on NEW state (after toggle)
    const openIcon = document.querySelector(".sidebar-icon-open");
    const closedIcon = document.querySelector(".sidebar-icon-closed");
    const isNowCollapsed =
      this.elements.sidebar?.classList.contains("collapsed");

    if (openIcon && closedIcon) {
      openIcon.style.display = isNowCollapsed ? "none" : "block";
      closedIcon.style.display = isNowCollapsed ? "block" : "none";
    }

    // Save state to localStorage
    localStorage.setItem("sisyphus-sidebar-collapsed", isNowCollapsed);
  }

  /**
   * Switch between tabs
   */
  switchTab(tabName) {
    // Update tab buttons
    this.elements.tabButtons.forEach((btn) => {
      const isActive = btn.dataset.tab === tabName;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive);
    });

    // Update tab content
    document.querySelectorAll(".tab-content").forEach((content) => {
      const isActive = content.id === `${tabName}Tab`;
      content.classList.toggle("active", isActive);
    });
  }

  /**
   * Handle input changes
   */
  handleInputChange() {
    this.autoResizeInput();
    this.updateSendButtonState();
  }

  /**
   * Auto-resize textarea
   */
  autoResizeInput() {
    if (this.elements.chatInput) {
      // Reset height to get accurate scrollHeight
      this.elements.chatInput.style.height = "24px";

      // Calculate new height (max 6 lines = ~120px)
      const newHeight = Math.min(this.elements.chatInput.scrollHeight, 120);
      this.elements.chatInput.style.height = newHeight + "px";
    }
  }

  /**
   * Update send button state
   */
  updateSendButtonState() {
    if (!this.elements.sendButton || !this.elements.chatInput) return;

    const hasText = this.elements.chatInput.value.trim().length > 0;
    this.elements.sendButton.disabled =
      !this.connected || !hasText || this.taskRunning;
  }

  /**
   * Handle window resize
   */
  handleResize() {
    // Adjust sidebar on mobile if needed
    if (window.innerWidth <= 768) {
      const isCollapsed = localStorage.getItem("sisyphus-sidebar-collapsed");
      if (isCollapsed === null) {
        this.elements.sidebar?.classList.add("collapsed");
      }
    }
  }

  /**
   * Handle visibility change
   */
  handleVisibilityChange() {
    if (document.hidden) {
      console.log("🔴 Page hidden, pausing updates");
    } else {
      console.log("🟢 Page visible, resuming updates");
      // Reconnect if disconnected while hidden
      if (!this.connected && this.ws?.readyState !== WebSocket.CONNECTING) {
        this.connect();
      }
    }
  }

  // ============================================
  // WebSocket Connection Management
  // ============================================

  /**
   * Connect to WebSocket server
   */
  connect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatus("Connecting...", false);
    console.log("🔌 Connecting to:", wsUrl);

    try {
      this.ws = new WebSocket(wsUrl);
      this.setupWebSocketHandlers();
    } catch (error) {
      console.error("❌ WebSocket creation failed:", error);
      this.handleConnectionError(error);
    }
  }

  /**
   * Setup WebSocket event handlers
   */
  setupWebSocketHandlers() {
    if (!this.ws) return;

    this.ws.onopen = () => this.handleOpen();
    this.ws.onmessage = (event) => this.handleMessage(event);
    this.ws.onerror = (error) => {
      console.error("❌ WebSocket error:", error);
      this.handleConnectionError(error);
    };
    this.ws.onclose = (event) => this.handleClose(event);
  }

  /**
   * Handle WebSocket open
   */
  handleOpen() {
    console.log("✅ WebSocket connected");
    this.connected = true;
    this.reconnectAttempts = 0;
    this.updateStatus("Connected", true);
    this.updateSendButtonState();

    // Send initialization message
    this.send({ type: "initialize", config: {} });
    this.addTerminalLine("=== Connected to Sisyphus Agent ===", "success");
  }

  /**
   * Handle incoming WebSocket messages
   */
  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      console.log("📨 Received:", message.type);

      // Message type handlers
      const handlers = {
        status: () => this.handleStatus(message),
        task_start: () => this.onTaskStart(message.task),
        task_end: () => this.onTaskEnd(),
        command: () => this.handleCommand(message),
        terminal: () => this.handleTerminal(message),
        frame: () => this.updateFrame(message.data, message.timestamp),
        stream_started: () => this.onStreamStarted(message.fps),
        stream_stopped: () => this.onStreamStopped(),
        error: () => this.handleError(message),
        command_history: () => this.handleCommandHistory(message),
      };

      const handler = handlers[message.type];
      if (handler) {
        handler();
      } else {
        console.warn("⚠️ Unknown message type:", message.type);
      }
    } catch (error) {
      console.error("❌ Message parsing error:", error);
      this.addTerminalLine(`Error parsing message: ${error.message}`, "error");
    }
  }

  /**
   * Handle WebSocket close
   */
  handleClose(event) {
    console.log("🔌 WebSocket closed:", event.code, event.reason);
    this.connected = false;
    this.updateStatus("Disconnected", false);
    this.updateSendButtonState();
    this.hideBrowser();

    this.addTerminalLine("=== Disconnected from agent ===", "error");

    // Attempt reconnection
    if (this.reconnectAttempts < this.maxReconnectAttempts && !event.wasClean) {
      this.reconnectAttempts++;
      const delay = Math.min(
        1000 * Math.pow(2, this.reconnectAttempts - 1),
        10000
      );

      this.addTerminalLine(
        `Reconnecting in ${delay / 1000}s... (Attempt ${
          this.reconnectAttempts
        }/${this.maxReconnectAttempts})`
      );

      this.reconnectTimeout = setTimeout(() => {
        if (!this.connected) {
          this.connect();
        }
      }, delay);
    } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.addTerminalLine(
        "Maximum reconnection attempts reached. Please refresh the page.",
        "error"
      );
      this.updateStatus("Connection Failed", false);
    }
  }

  /**
   * Handle connection error
   */
  handleConnectionError(error) {
    this.updateStatus("Connection Failed", false);
    this.addTerminalLine(
      `Failed to connect: ${error.message || error}`,
      "error"
    );
  }

  // ============================================
  // Message Handlers
  // ============================================

  /**
   * Handle status message
   */
  handleStatus(message) {
    if (message.ready) {
      this.updateStatus(message.message || "Ready", true);
      this.addTerminalLine(message.message || "Agent ready", "success");
    } else {
      this.addTerminalLine(message.message || "Initializing...");
    }
  }

  /**
   * Handle command message
   */
  handleCommand(message) {
    this.addCommand(message.step, message.command, message.thinking);
    this.addTerminalLine(`[Step ${message.step}] ${message.command}`);

    if (message.thinking) {
      this.addTerminalLine(`  → ${message.thinking}`);
    }
  }

  /**
   * Handle terminal output
   */
  handleTerminal(message) {
    const content = message.content || "";
    if (content.trim()) {
      this.addTerminalLine(content);
    }
  }

  /**
   * Handle error message
   */
  handleError(message) {
    this.addTerminalLine(`ERROR: ${message.message}`, "error");
  }

  /**
   * Handle command history
   */
  handleCommandHistory(message) {
    if (message.commands && Array.isArray(message.commands)) {
      console.log(
        "📋 Command history updated:",
        message.commands.length,
        "commands"
      );
    }
  }

  /**
   * Handle stream started
   */
  onStreamStarted(fps) {
    console.log(`📹 Stream started at ${fps} FPS`);
    this.addTerminalLine(
      `Browser stream started at ${fps || 60} FPS`,
      "success"
    );
  }

  /**
   * Handle stream stopped
   */
  onStreamStopped() {
    console.log("⏹️ Stream stopped");
    this.hideBrowser();
    this.addTerminalLine("Browser stream stopped");
  }

  // ============================================
  // Send Messages
  // ============================================

  /**
   * Send message to server
   */
  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        console.log("📤 Sent:", message.type);
        return true;
      } catch (error) {
        console.error("❌ Failed to send message:", error);
        return false;
      }
    } else {
      console.error("❌ Cannot send - WebSocket state:", this.ws?.readyState);
      this.addTerminalLine(
        "Cannot send message - not connected to server",
        "error"
      );
      return false;
    }
  }

  /**
   * Send user message
   */
  sendMessage() {
    const message = this.elements.chatInput?.value.trim();
    if (!message || !this.connected || this.taskRunning) {
      return;
    }

    // Add to terminal
    this.addTerminalLine(`> ${message}`, "success");

    // Add to commands tab
    this.addUserCommand(message);

    // Clear input
    if (this.elements.chatInput) {
      this.elements.chatInput.value = "";
      this.elements.chatInput.style.height = "24px";
      this.updateSendButtonState();
    }

    // Send execute task command
    this.send({
      type: "execute_task",
      task: message,
    });
  }

  /**
   * Add user command to history
   */
  addUserCommand(command) {
    if (!this.elements.commandsList) return;

    // Remove empty state if present
    const emptyState = this.elements.commandsList.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    const commandItem = document.createElement("div");
    commandItem.className = "command-item user-command";

    commandItem.innerHTML = `
      <div class="command-step success">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
        USER INPUT
      </div>
      <div class="command-text">${this.escapeHtml(command)}</div>
      <div class="command-reasoning">Command sent to agent</div>
    `;

    this.elements.commandsList.appendChild(commandItem);
    this.elements.commandsList.scrollTop =
      this.elements.commandsList.scrollHeight;
  }

  /**
   * Stop current task - FIXED: Immediate sending
   */
  stopTask() {
    console.log("🛑🛑🛑 stopTask() called");

    // Check if task is actually running
    if (!this.taskRunning) {
      console.log("⚠️ No task running, ignoring stop");
      return;
    }

    // Add terminal feedback IMMEDIATELY
    this.addTerminalLine("Stopping task...", "error");

    // Send stop message with IMMEDIATE priority
    const stopMessage = { type: "stop_task" };

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        // Send immediately - don't queue
        this.ws.send(JSON.stringify(stopMessage));
        console.log("✅ Stop message sent immediately");
      } catch (error) {
        console.error("❌ Failed to send stop:", error);
      }
    } else {
      console.error(
        "❌ Cannot stop - WebSocket not open:",
        this.ws?.readyState
      );
    }

    // Update UI immediately (don't wait for server response)
    this.taskRunning = false;
    this.updateButtonStates(false);
  }

  // ============================================
  // Task State Management
  // ============================================

  /**
   * Handle task start
   */
  onTaskStart(task) {
    console.log("▶️ Task started:", task);
    this.taskRunning = true;
    this.updateButtonStates(true);

    this.addTerminalLine("─".repeat(60));
    this.addTerminalLine(`Executing task: ${task}`, "success");
  }

  /**
   * Handle task end
   */
  onTaskEnd() {
    console.log("⏹️ Task ended");
    this.taskRunning = false;
    this.updateButtonStates(false);

    this.addTerminalLine("Task completed", "success");
    this.addTerminalLine("─".repeat(60));

    // Add task completion notification to commands list
    this.addTaskCompleteNotification();

    // Focus input for next command
    setTimeout(() => {
      this.elements.chatInput?.focus();
    }, 100);
  }

  /**
   * Add task complete notification to commands list
   */
  addTaskCompleteNotification() {
    if (!this.elements.commandsList) return;

    // Remove empty state if present
    const emptyState = this.elements.commandsList.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    const commandItem = document.createElement("div");
    commandItem.className = "command-item task-complete";

    const timestamp = this.formatTime(new Date());

    commandItem.innerHTML = `
      <div class="command-step info">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        TASK COMPLETED
      </div>
      <div class="command-text">Task finished successfully at ${timestamp}</div>
      <div class="command-reasoning">All steps executed and task completed</div>
    `;

    this.elements.commandsList.appendChild(commandItem);
    this.elements.commandsList.scrollTop =
      this.elements.commandsList.scrollHeight;
  }

  /**
   * Update button states based on task running
   */
  updateButtonStates(isRunning) {
    if (this.elements.sendButton) {
      this.elements.sendButton.style.display = isRunning ? "none" : "flex";
    }
    if (this.elements.stopButton) {
      this.elements.stopButton.style.display = isRunning ? "flex" : "none";
    }
    if (this.elements.chatInput) {
      this.elements.chatInput.disabled = isRunning;
    }

    this.updateSendButtonState();
  }

  // ============================================
  // UI Updates
  // ============================================

  /**
   * Update connection status
   */
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

  /**
   * Update browser frame
   */
  updateFrame(dataUrl, timestamp) {
    if (!dataUrl) return;

    if (this.elements.browserFrame) {
      this.elements.browserFrame.src = dataUrl;
      this.elements.browserFrame.classList.add("visible");
    }

    if (this.elements.viewportPlaceholder) {
      this.elements.viewportPlaceholder.style.display = "none";
    }

    this.frameCount++;
    this.lastFrameTime = Date.now();

    // Update latency counter
    if (timestamp && this.elements.latencyCounter) {
      const latency = Date.now() - timestamp * 1000;
      if (latency >= 0 && latency < 5000) {
        this.elements.latencyCounter.textContent = `${Math.round(latency)}ms`;
        this.elements.latencyCounter.classList.add("active");
      }
    }
  }

  /**
   * Hide browser viewport
   */
  hideBrowser() {
    if (this.elements.browserFrame) {
      this.elements.browserFrame.classList.remove("visible");
      this.elements.browserFrame.src = "";
    }

    if (this.elements.viewportPlaceholder) {
      this.elements.viewportPlaceholder.style.display = "flex";
    }

    if (this.elements.latencyCounter) {
      this.elements.latencyCounter.textContent = "--";
      this.elements.latencyCounter.classList.remove("active");
    }

    if (this.elements.fpsCounter) {
      this.elements.fpsCounter.textContent = "--";
      this.elements.fpsCounter.classList.remove("active");
    }
  }

  /**
   * Start performance monitoring
   */
  startPerformanceMonitoring() {
    setInterval(() => {
      if (this.elements.fpsCounter) {
        if (this.frameCount > 0) {
          this.elements.fpsCounter.textContent = `${this.frameCount} FPS`;
          this.elements.fpsCounter.classList.add("active");
          this.frameCount = 0;
        } else {
          // Check if we haven't received a frame in a while
          const timeSinceLastFrame = Date.now() - this.lastFrameTime;
          if (timeSinceLastFrame > 2000) {
            this.elements.fpsCounter.textContent = "--";
            this.elements.fpsCounter.classList.remove("active");
          }
        }
      }
    }, 1000);
  }

  // ============================================
  // Terminal Management
  // ============================================

  /**
   * Add line to terminal
   */
  addTerminalLine(text, type = "") {
    if (!this.elements.terminal) return;

    const line = document.createElement("div");
    line.className = `terminal-line ${type}`;
    line.textContent = `[${this.formatTime(new Date())}] ${text}`;

    this.elements.terminal.appendChild(line);

    // Auto-scroll to bottom
    this.elements.terminal.scrollTop = this.elements.terminal.scrollHeight;

    // Limit terminal history to prevent memory issues
    const lines = this.elements.terminal.querySelectorAll(".terminal-line");
    if (lines.length > 1000) {
      lines[0].remove();
    }
  }

  /**
   * Clear terminal
   */
  clearTerminal() {
    if (this.elements.terminal) {
      this.elements.terminal.innerHTML = "";
      this.addTerminalLine("Terminal cleared");
    }
  }

  // ============================================
  // Commands Management
  // ============================================

  /**
   * Add command to history
   */
  addCommand(step, command, thinking) {
    if (!this.elements.commandsList) return;

    // Remove empty state if present
    const emptyState = this.elements.commandsList.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    const commandItem = document.createElement("div");
    commandItem.className = "command-item";
    commandItem.setAttribute("role", "article");
    commandItem.setAttribute("aria-label", `Command step ${step}`);

    commandItem.innerHTML = `
      <div class="command-step">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
          <polyline points="9 11 12 14 22 4"></polyline>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        STEP ${step}
      </div>
      <div class="command-text">${this.escapeHtml(command)}</div>
      ${
        thinking
          ? `<div class="command-reasoning">${this.escapeHtml(thinking)}</div>`
          : ""
      }
    `;

    this.elements.commandsList.appendChild(commandItem);

    // Auto-scroll to bottom
    this.elements.commandsList.scrollTop =
      this.elements.commandsList.scrollHeight;

    // Limit command history
    const items = this.elements.commandsList.querySelectorAll(".command-item");
    if (items.length > 100) {
      items[0].remove();
    }
  }

  /**
   * Clear commands history
   */
  clearCommands() {
    if (this.elements.commandsList) {
      this.elements.commandsList.innerHTML = `
        <div class="empty-state">
          <svg
            width="56"
            height="56"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p>No commands executed yet</p>
        </div>
      `;
    }
  }

  // ============================================
  // Utility Methods
  // ============================================

  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Format time for terminal output
   */
  formatTime(date) {
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  /**
   * Debounce function for performance
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * Cleanup on page unload
   */
  cleanup() {
    if (this.ws) {
      this.ws.close();
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }
  }
}

// ============================================
// Initialize Application
// ============================================

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 DOM loaded, initializing Sisyphus Agent...");

  // Create global instance
  window.sisyphusAgent = new SisyphusAgent();

  // Cleanup on page unload
  window.addEventListener("beforeunload", () => {
    window.sisyphusAgent?.cleanup();
  });
});

// Handle service worker if needed (for PWA support in future)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    // Service worker registration can be added here if needed
  });
}

// Export for module usage if needed
if (typeof module !== "undefined" && module.exports) {
  module.exports = SisyphusAgent;
}
