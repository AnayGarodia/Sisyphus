from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
from rich.logging import RichHandler
import logging
import shlex
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=Console(stderr=True))]
)

# Create separate loggers for different purposes
command_logger = logging.getLogger("commands")
action_logger = logging.getLogger("actions") 
error_logger = logging.getLogger("errors")

def parse_command(command_line: str) -> List[str]:
    try:
        return shlex.split(command_line)
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] Invalid command syntax: {e}")
        console.print("[bold yellow][TIP][/bold yellow] Use quotes for text with spaces: type 1 'hello world'")
        return []  # Return empty list to signal error

console = Console()

class BaseBrowserAgent:

    DEFAULT_TIMEOUT = 30000
    DEFAULT_SHORT_WAIT = 500


    def __init__(self, headless=False, timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.playwright = sync_playwright().start()
        
        # Enhanced browser context to avoid detection
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )
        
        # Create context with human-like settings
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = self.context.new_page()
        
        # Hide automation indicators
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        self.page.add_init_script("""
            // Override window.open
            window.open = function(url, target, features) {
                if (url) {
                    window.location.href = url;
                }
                return window;
            };
            
            // Override target="_blank"
            document.addEventListener('click', function(e) {
                if (e.target.tagName === 'A' && e.target.target === '_blank') {
                    e.preventDefault();
                    window.location.href = e.target.href;
                }
            }, true);
        """)
        
        # Rest of your initialization code...
        self.command_history: List[Dict[str, Any]] = []
        self.action_count = 0
        self.element_map = {}
        
        action_logger.info("Browser started successfully")
        console.print("[bold green][INFO][/bold green] Browser started. Type 'help' for commands.")

    # LOGGING METHODS
    def log_command(self, cmd: str, args: List[str], success: bool = True, error: str = None):
        """Log command execution with timestamp and details"""
        timestamp = datetime.now().isoformat()
        command_entry = {
            'timestamp': timestamp,
            'command': cmd,
            'args': args,
            'success': success,
            'error': error,
            'action_id': self.action_count
        }
        
        self.command_history.append(command_entry)
        self.action_count += 1
        
        # Log to appropriate logger
        if success:
            command_logger.info(f"[{self.action_count}] {cmd} {' '.join(args)}")
        else:
            error_logger.error(f"[{self.action_count}] FAILED: {cmd} {' '.join(args)} - {error}")

    def log_action(self, action: str, details: str = "", success: bool = True):
        """Log browser actions (navigation, clicks, etc.)"""
        if success:
            action_logger.info(f"Action: {action} - {details}")
        else:
            error_logger.error(f"Action Failed: {action} - {details}")

    def get_command_history(self, limit=10):
        """Get recent command history"""
        if isinstance(limit, str):
            limit = int(limit) if limit.isdigit() else 10
        elif limit is None:
            limit = 10
        recent = self.command_history[-limit:]
        console.print("\n[bold cyan]Recent Commands:[/bold cyan]")
        for entry in recent:
            status = "âœ“" if entry['success'] else "âœ—"
            console.print(f"  {status} [{entry['action_id']}] {entry['command']} {' '.join(entry['args'])}")

    def get_action_stats(self):
        """Get statistics about actions performed"""
        total_commands = len(self.command_history)
        successful = sum(1 for cmd in self.command_history if cmd['success'])
        failed = total_commands - successful
        
        console.print(f"\n[bold cyan]Action Statistics:[/bold cyan]")
        console.print(f"  Total Commands: {total_commands}")
        console.print(f"  Successful: {successful}")
        console.print(f"  Failed: {failed}")

    # BROWSER ACTIONS
    def _get_element(self, selector):
        """Get element by index, label, or CSS selector
        
        Args:
            selector: Can be int (index), str (digit/label/CSS)
        
        Returns:
            ElementHandle or None
        """
        # Case 1: Direct integer
        if isinstance(selector, int):
            if hasattr(self, "element_map") and selector in self.element_map:
                return self.element_map[selector]["handle"]
            return None
        
        # Case 2: String input
        if isinstance(selector, str):
            selector_clean = selector.strip()
            
            # Case 2a: String that's a number (like "7")
            if selector_clean.isdigit():
                idx = int(selector_clean)
                if hasattr(self, "element_map") and idx in self.element_map:
                    return self.element_map[idx]["handle"]
                return None
            
            # Case 2b: Try label match (remove quotes if present)
            selector_clean = selector_clean.strip('"').strip("'")
            if hasattr(self, "element_map"):
                for meta in self.element_map.values():
                    if meta["label"].lower() == selector_clean.lower():
                        return meta["handle"]
            
            # Case 2c: Try as CSS selector
            try:
                return self.page.query_selector(selector_clean)
            except:
                return None
        
        return None
    def go_to(self, url: str):
        """Navigate to URL"""
        try:
            if not url.startswith(("http://", "https://")):
                url = "http://" + url

            self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            self.log_action("navigate", f"URL: {url}, Title: {self.page.title()}", success=True)
            console.print(f"[bold green][INFO][/bold green] Navigated to {url}")

        except Exception as e:
            self.log_action("navigate", f"URL: {url}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to navigate to {url}: {str(e)}")

    def close(self):
        try: 
            action_logger.info(f"Session ended. Total actions: {self.action_count}")
            self.context.close()
            self.browser.close()
            self.playwright.stop()
            console.print("[bold green][INFO][/bold green] Browser closed.")

        except Exception as e:
            error_logger.error(f"Error closing browser: {str(e)}")
            console.print(f"[bold red][ERROR][/bold red] Error closing browser: {str(e)}")
    
    def refresh(self):
        """Reload the current page."""
        try:
            self.page.reload(wait_until="domcontentloaded", timeout=self.timeout)
            self.log_action("refresh", f"URL: {self.page.url}", success=True)
            console.print(f"[bold green][INFO][/bold green] Page refreshed: {self.page.url}")
        except Exception as e:
            self.log_action("refresh", f"URL: {self.page.url}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to refresh page: {str(e)}")

    def back(self):
        """Navigate to the previous page in browser history."""
        try:
            response = self.page.go_back(wait_until="domcontentloaded", timeout=self.timeout)
            if response is not None:
                self.log_action("back", f"URL: {self.page.url}", success=True)
                console.print(f"[bold green][INFO][/bold green] Navigated back to: {self.page.url}")
            else:
                self.log_action("back", f"URL: {self.page.url}", success=False)
                console.print(f"[bold yellow][WARN][/bold yellow] Cannot navigate back (no previous page or cross-origin).")
        except Exception as e:
            self.log_action("back", f"URL: {self.page.url}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to go back: {str(e)}")

    def forward(self):
        """Navigate to the next page in browser history."""
        try:
            response = self.page.go_forward(wait_until="domcontentloaded", timeout=self.timeout)
            if response is not None:
                self.log_action("forward", f"URL: {self.page.url}", success=True)
                console.print(f"[bold green][INFO][/bold green] Navigated forward to: {self.page.url}")
            else:
                self.log_action("forward", f"URL: {self.page.url}", success=False)
                console.print(f"[bold yellow][WARN][/bold yellow] Cannot navigate forward (no next page or cross-origin).")
        except Exception as e:
            self.log_action("forward", f"URL: {self.page.url}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to go forward: {str(e)}")

    def stop(self):
        """Stop the page loading."""
        try:
            self.page.context._impl_obj._channel.send("Page.stopLoading")
            self.log_action("stop", f"URL: {self.page.url}", success=True)
            console.print(f"[bold green][INFO][/bold green] Stopped page loading: {self.page.url}")
        except Exception as e:
            self.log_action("stop", f"URL: {self.page.url}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to stop page loading: {str(e)}")

    def home(self):
        """Navigate to the homepage (default to https://www.google.com)."""
        homepage = "https://www.google.com"
        try:
            self.page.goto(homepage, wait_until="domcontentloaded", timeout=self.timeout)
            self.log_action("home", f"URL: {homepage}", success=True)
            console.print(f"[bold green][INFO][/bold green] Navigated to homepage: {homepage}")
        except Exception as e:
            self.log_action("home", f"URL: {homepage}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to navigate to homepage: {str(e)}")

    def url(self):
        """Get the current page URL."""
        try:
            current_url = self.page.url
            self.log_action("url", f"URL: {current_url}", success=True)
            console.print(f"[bold cyan][INFO][/bold cyan] Current URL: {current_url}")
            return current_url
        except Exception as e:
            self.log_action("url", "Failed to get current URL", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to get current URL: {str(e)}")
            return None

    def title(self):
        """Get the current page title."""
        try:
            page_title = self.page.title()
            self.log_action("title", f"Title: {page_title}", success=True)
            console.print(f"[bold cyan][INFO][/bold cyan] Page Title: {page_title}")
            return page_title
        except Exception as e:
            self.log_action("title", "Failed to get page title", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to get page title: {str(e)}")
            return None

    def history_list(self):
        """Get the complete browser navigation history including all navigation actions."""
        try:
            console.print("\n[bold cyan]Complete Navigation History:[/bold cyan]")
            console.print("=" * 80)
            
            navigation_entries = []
            
            # Track all navigation-related commands
            for entry in self.command_history:
                if entry['command'] in ['go', 'go_to', 'back', 'forward', 'home', 'refresh']:
                    status = "âœ“" if entry['success'] else "âœ—"
                    timestamp = entry['timestamp'].split('T')[1].split('.')[0]  # Just time part
                    
                    if entry['command'] in ['go', 'go_to'] and entry['args']:
                        url = entry['args'][0]
                        if not url.startswith(("http://", "https://")):
                            url = "http://" + url
                        action = f"Navigate to: {url}"
                    elif entry['command'] == 'back':
                        action = "Back in history"
                    elif entry['command'] == 'forward':
                        action = "Forward in history"
                    elif entry['command'] == 'home':
                        action = "Navigate to: https://www.google.com"
                    elif entry['command'] == 'refresh':
                        action = "Page refreshed"
                    else:
                        action = entry['command']
                    
                    navigation_entries.append({
                        'status': status,
                        'timestamp': timestamp,
                        'action': action,
                        'success': entry['success']
                    })
            
            if not navigation_entries:
                console.print("[bold yellow][INFO][/bold yellow] No navigation history found.")
                return
            
            # Display entries
            for i, entry in enumerate(navigation_entries, 1):
                color = "[green]" if entry['success'] else "[red]"
                console.print(f"  {entry['status']} [{entry['timestamp']}] {color}{entry['action']}[/{color.strip('[]')}]")
            
            console.print("=" * 80)
            console.print(f"[bold green][INFO][/bold green] Total navigation actions: {len(navigation_entries)}")
            
            self.log_action("history_list", "Displayed complete navigation history", success=True)
            
        except Exception as e:
            self.log_action("history_list", "Failed to display navigation history", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to display navigation history: {str(e)}")

    def right_click(self, selector):
        """Right-click an element by selector or element ID"""
        try:
            element = self._get_element(selector)  # Use helper
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                return False
            
            element.click(button='right')
            console.print(f"[bold green][INFO][/bold green] Right-clicked element {selector}")
            self.log_action("right_click", f"Selector: {selector}", success=True)
            return True
            
        except Exception as e:
            self.log_action("right_click", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to right-click {selector}: {str(e)}")
            return False;

    def type(self, selector, text, clear_first=True):
        """Type text into an input field"""
        try:
            element = self._get_element(selector)
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                return False
            
            # Verify it's an input
            is_input = element.evaluate("""
                el => {
                    return el.tagName === 'INPUT' || 
                        el.tagName === 'TEXTAREA' ||
                        el.contentEditable === 'true' ||
                        el.getAttribute('role') === 'textbox';
                }
            """)
            
            if not is_input:
                console.print(f"[bold red][ERROR][/bold red] Element is not an input field")
                return False
            
            # Clear and type
            element.click()
            element.fill('')  # Playwright's fill() is reliable
            element.type(text, delay=50)
            
            console.print(f"[bold green][INFO][/bold green] Typed into {selector}")
            self.log_action("type", f"Selector: {selector}, Length: {len(text)}", success=True)
            return True
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Failed to type: {e}")
            self.log_action("type", f"Selector: {selector}", success=False)
            return False

    def double_click(self, selector):
        """Double-click an element by selector or element ID"""
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                if isinstance(selector, (int, str)) and str(selector).strip().isdigit():
                    console.print(f"[bold yellow][TIP][/bold yellow] Run 'scan' first to see available elements")
                self.log_action("double_click", f"Selector: {selector}", success=False)
                return False
            
            element.dblclick()
            console.print(f"[bold green][INFO][/bold green] Double-clicked element {selector}")
            self.log_action("double_click", f"Selector: {selector}", success=True)
            return True
            
        except Exception as e:
            self.log_action("double_click", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to double-click {selector}: {str(e)}")
            return False

    def middle_click(self, selector):
        """Middle-click an element by selector or element ID"""
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                if isinstance(selector, (int, str)) and str(selector).strip().isdigit():
                    console.print(f"[bold yellow][TIP][/bold yellow] Run 'scan' first to see available elements")
                self.log_action("middle_click", f"Selector: {selector}", success=False)
                return False
            
            element.click(button='middle')
            console.print(f"[bold green][INFO][/bold green] Middle-clicked element {selector}")
            self.log_action("middle_click", f"Selector: {selector}", success=True)
            return True
            
        except Exception as e:
            self.log_action("middle_click", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to middle-click {selector}: {str(e)}")
            return False