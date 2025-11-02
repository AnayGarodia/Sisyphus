"""
Base browser agent with core functionality - FIXED VERSION.
Key fixes:
- Added framework-agnostic property accessors
- Improved element resolution
- Added page health checks
- Fixed timeout handling in cleanup
"""

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeout
from rich.console import Console
from rich.logging import RichHandler
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import shlex
import sys
import os

console = Console()

def _setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a properly configured logger with Rich handler."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    handler = RichHandler(
        console=Console(stderr=True),
        show_path=False,
        markup=True,
        show_time=False
    )
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger

command_logger = _setup_logger("commands", logging.INFO)
action_logger = _setup_logger("actions", logging.INFO)
error_logger = _setup_logger("errors", logging.ERROR)

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


class BaseBrowserAgent:
    """
    Core browser agent with Playwright integration.
    
    Key improvements:
    - Framework-agnostic property accessors
    - Health checks before operations
    - Proper timeout handling
    - Better element resolution
    """
    
    DEFAULT_TIMEOUT = 30000  # 30 seconds
    CLEANUP_TIMEOUT = 5000   # 5 seconds for cleanup operations
    
    def __init__(self, headless: bool = False, timeout: int = DEFAULT_TIMEOUT):
        """Initialize browser with error handling."""
        self.timeout = timeout
        self.playwright = None
        self.browser = None
        self.context = None

        self.page = None
        self._is_healthy = False
        
        self._navigation_stack: List[str] = []  # For NavigationMixin
        self._page_load_metrics: Dict[str, Any] = {}  # For NavigationMixin
        self._element_registry = {}  # For ScanningMixin (might already be in __init__)
        self._next_index = 1
        
        try:
            self.playwright = sync_playwright().start()
            
            self.browser: Browser = self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            
            self.context: BrowserContext = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            self.page: Page = self.context.new_page()
            self.page.set_default_timeout(timeout)
            
            # Anti-detection
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                window.open = function(url) {
                    if (url) window.location.href = url;
                    return window;
                };
            """)
            
            # State
            self.command_history: List[Dict[str, Any]] = []
            self.action_count: int = 0
            self.element_map: Dict[int, Dict[str, Any]] = {}
            
            self._is_healthy = True
            action_logger.info("Browser initialized")
            console.print("[green]Ready.[/green] Type 'help' for commands.")
            
        except Exception as e:
            self._cleanup()
            raise RuntimeError(f"Browser initialization failed: {e}")
    
    # ==================== Framework-Agnostic Accessors ====================
    
    def get_current_url(self) -> str:
        """Get current URL safely."""
        self._ensure_healthy()
        try:
            return self.page.url
        except Exception as e:
            error_logger.debug(f"Failed to get URL: {e}")
            return "about:blank"
    
    def get_page_title(self) -> str:
        """Get page title safely."""
        self._ensure_healthy()
        try:
            return self.page.title()
        except Exception as e:
            error_logger.debug(f"Failed to get title: {e}")
            return ""
    
    def is_page_loaded(self) -> bool:
        """Check if page is in usable state."""
        try:
            return self.page and not self.page.is_closed() and self._is_healthy
        except:
            return False
    
    def _ensure_healthy(self):
        """Verify browser is in working state."""
        if not self._is_healthy:
            raise RuntimeError("Browser is not healthy - restart required")
        
        if not self.page or self.page.is_closed():
            self._is_healthy = False
            raise RuntimeError("Page closed - browser needs restart")
    
    # ==================== Element Resolution ====================
    
    def _get_element(self, selector):
        """
        Resolve element by index, label, or CSS selector.
        PUBLIC method (not private).
        
        Args:
            selector: int, str (numeric), label, or CSS selector
        
        Returns:
            ElementHandle or None
        """
        self._ensure_healthy()
        
        # Normalize to int if possible
        if isinstance(selector, str):
            selector = selector.strip().strip('"').strip("'")
            if selector.isdigit():
                selector = int(selector)
        
        # Integer index lookup
        if isinstance(selector, int):
            meta = self.element_map.get(selector)
            if not meta:
                return None
            
            # Verify element is still attached
            handle = meta.get("handle")
            try:
                if handle and not handle.is_hidden():
                    return handle
            except:
                # Element went stale
                return None
            
            return None
        
        # String handling - label match or CSS
        if isinstance(selector, str):
            # Try label match (case-insensitive)
            for meta in self.element_map.values():
                if meta["label"].lower() == selector.lower():
                    handle = meta.get("handle")
                    try:
                        if handle and not handle.is_hidden():
                            return handle
                    except:
                        continue
            
            # Try CSS selector as fallback
            try:
                return self.page.query_selector(selector)
            except Exception:
                return None
        
        return None
    
    # ==================== Cleanup ====================
    
    def _cleanup(self):
        """Internal cleanup with timeouts."""
        errors = []
        
        # Mark as unhealthy immediately
        self._is_healthy = False
        
        if self.page:
            try:
                self.page.close(timeout=self.CLEANUP_TIMEOUT)
            except Exception as e:
                errors.append(f"page: {e}")
        
        if self.context:
            try:
                self.context.close(timeout=self.CLEANUP_TIMEOUT)
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
        self.action_count += 1
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'command': cmd,
            'args': [str(a) for a in args],
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
        """PUBLIC command parser (was private)."""
        return parse_command(command_line)