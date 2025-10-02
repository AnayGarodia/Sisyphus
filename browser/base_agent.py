"""
Base browser agent with core functionality.
Handles initialization, logging, state management, and cleanup.
All commands are implemented in mixin classes.
"""

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from rich.console import Console
from rich.logging import RichHandler
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import shlex
import sys

# ==================== Console Setup ====================
console = Console()

# ==================== Logging Setup ====================
# Each logger has its own handler with distinct level/output

def _setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a properly configured logger with Rich handler."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # RichHandler manages its own formatting - don't override
    handler = RichHandler(
        console=Console(stderr=True),
        show_path=False,
        markup=True,
        show_time=False  # We add timestamps ourselves when needed
    )
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger

command_logger = _setup_logger("commands", logging.INFO)
action_logger = _setup_logger("actions", logging.INFO)
error_logger = _setup_logger("errors", logging.ERROR)


# ==================== Utility Functions ====================

def parse_command(command_line: str) -> Optional[List[str]]:
    """
    Parse command line input respecting quotes.
    Returns None on parse error (vs empty list for empty input).
    """
    if not command_line.strip():
        return []
    
    try:
        return shlex.split(command_line)
    except ValueError as e:
        console.print(f"[bold red]Parse Error:[/bold red] {e}")
        console.print("[dim]Tip: Use quotes for text with spaces: type 1 'hello world'[/dim]")
        return None


# ==================== Base Agent ====================

class BaseBrowserAgent:
    """
    Core browser agent with Playwright integration.
    
    Responsibilities:
    - Browser lifecycle (init, cleanup)
    - Logging infrastructure
    - State management (history, element map)
    
    Does NOT implement commands - those are in mixins.
    
    Usage:
        with BaseBrowserAgent() as agent:
            agent.go_to("example.com")
    """
    
    DEFAULT_TIMEOUT = 30000  # 30 seconds
    
    def __init__(self, headless: bool = False, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize browser. Opens Chromium immediately.
        
        Args:
            headless: Run without GUI
            timeout: Default navigation timeout (ms)
        
        Raises:
            RuntimeError: If browser launch fails
        """
        self.timeout = timeout
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        try:
            self.playwright = sync_playwright().start()
            
            self.browser: Browser = self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            
            # Realistic browser context
            self.context: BrowserContext = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            self.page: Page = self.context.new_page()
            
            # Basic anti-detection
            self.page.add_init_script("""
                // Hide webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Prevent new tabs/windows
                window.open = function(url) {
                    if (url) window.location.href = url;
                    return window;
                };
            """)
            
            # State
            self.command_history: List[Dict[str, Any]] = []
            self.action_count: int = 0
            self.element_map: Dict[int, Dict[str, Any]] = {}
            
            action_logger.info("Browser initialized")
            console.print("[green]Ready.[/green] Type 'help' for commands.")
            
        except Exception as e:
            # Cleanup on init failure
            self._cleanup()
            raise RuntimeError(f"Browser initialization failed: {e}")
    
    def _cleanup(self):
        """Internal cleanup - closes resources in reverse order."""
        errors = []
        
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                errors.append(f"page: {e}")
        
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                errors.append(f"context: {e}")
        
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                errors.append(f"browser: {e}")
        
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                errors.append(f"playwright: {e}")
        
        if errors:
            error_logger.error(f"Cleanup errors: {', '.join(errors)}")
    
    # ==================== Context Manager ====================
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    # ==================== Logging ====================
    
    def log_command(self, cmd: str, args: List[str], success: bool = True, error: Optional[str] = None):
        """Log command execution."""
        self.action_count += 1  # Increment FIRST
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'command': cmd,
            'args': [str(a) for a in args],  # Ensure strings
            'success': success,
            'error': error,
            'action_id': self.action_count
        }
        
        self.command_history.append(entry)
        
        args_str = ' '.join(entry['args'])
        if success:
            command_logger.info(f"[{self.action_count}] {cmd} {args_str}")
        else:
            error_logger.error(f"[{self.action_count}] {cmd} {args_str} - {error}")
    
    def log_action(self, action: str, details: str = "", success: bool = True):
        """Log browser actions."""
        msg = f"{action}: {details}" if details else action
        
        if success:
            action_logger.info(msg)
        else:
            error_logger.error(f"{action} FAILED: {details}")
    
    # ==================== History & Stats ====================
    
    def get_command_history(self, limit: int = 10):
        """Display recent commands."""
        if isinstance(limit, str):
            if not limit.isdigit():
                console.print(f"[yellow]Invalid limit '{limit}', using 10[/yellow]")
                limit = 10
            else:
                limit = int(limit)
        
        recent = self.command_history[-limit:]
        
        if not recent:
            console.print("[yellow]No command history yet[/yellow]")
            return
        
        console.print("\n[bold cyan]Recent Commands:[/bold cyan]")
        
        for entry in recent:
            status = "+" if entry['success'] else "x"
            color = "green" if entry['success'] else "red"
            args_str = ' '.join(entry['args'])
            cmd_display = f"{entry['command']} {args_str}".strip()
            
            console.print(f"[{color}]{status}[/{color}] [{entry['action_id']:3}] {cmd_display}")
        
        console.print()
    
    def get_action_stats(self):
        """Display session statistics."""
        total = len(self.command_history)
        
        if total == 0:
            console.print("[yellow]No actions performed yet[/yellow]")
            return
        
        successful = sum(1 for cmd in self.command_history if cmd['success'])
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0
        
        console.print("\n[bold cyan]Session Statistics:[/bold cyan]")
        console.print(f"  Total:    {total}")
        console.print(f"  Success:  {successful} ({success_rate:.1f}%)")
        console.print(f"  Failed:   {failed}")
        console.print(f"  Mapped:   {len(self.element_map)} elements")
        console.print()
    
    # ==================== Cleanup ====================
    
    def close(self):
        """Clean shutdown. Safe to call multiple times."""
        try:
            action_logger.info(f"Session ended. Actions: {self.action_count}")
            self._cleanup()
            console.print("[green]Browser closed[/green]")
        except Exception as e:
            error_logger.error(f"Shutdown error: {e}")
    
    def _parse_command_line(self, command_line: str):
        """
        Parse command line using the parse_command utility.
        Wrapper for logging purposes.
        """
        return parse_command(command_line)

    def _get_element(self, selector):
        """
        Resolve element by index, label, or CSS selector.
        
        Args:
            selector: int (element_map index), str (label or CSS)
        
        Returns:
            ElementHandle or None
        """
        # Integer index
        if isinstance(selector, int):
            return self.element_map.get(selector, {}).get("handle")
        
        # String handling
        if isinstance(selector, str):
            selector = selector.strip().strip('"').strip("'")
            
            # Numeric string -> index lookup
            if selector.isdigit():
                idx = int(selector)
                return self.element_map.get(idx, {}).get("handle")
            
            # Label match (case-insensitive)
            for meta in self.element_map.values():
                if meta["label"].lower() == selector.lower():
                    return meta["handle"]
            
            # CSS selector fallback
            try:
                return self.page.query_selector(selector)
            except Exception:
                return None
        
        return None