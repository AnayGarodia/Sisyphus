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
    except ValueError:
        return command_line.split()

console = Console()

class BaseBrowserAgent:
    def __init__(self, headless=False):
        self.playwright = sync_playwright().start()
        
        # Enhanced browser context to avoid detection
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--start-maximized'
            ]
        )
        
        # Create context with human-like settings
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive'
            },
            java_script_enabled=True,
            permissions=['geolocation', 'notifications']
        )
        
        self.page = self.context.new_page()
        
        # Hide automation indicators
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            window.chrome = {
                runtime: {},
            };
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
            status = "✓" if entry['success'] else "✗"
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
    def go_to(self, url: str):
        """Navigate to URL"""
        try:
            if not url.startswith(("http://", "https://")):
                url = "http://" + url

            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

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
            self.page.reload(wait_until="domcontentloaded", timeout=30000)
            self.log_action("refresh", f"URL: {self.page.url}", success=True)
            console.print(f"[bold green][INFO][/bold green] Page refreshed: {self.page.url}")
        except Exception as e:
            self.log_action("refresh", f"URL: {self.page.url}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to refresh page: {str(e)}")

    def back(self):
        """Navigate to the previous page in browser history."""
        try:
            response = self.page.go_back(wait_until="domcontentloaded", timeout=30000)
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
            response = self.page.go_forward(wait_until="domcontentloaded", timeout=30000)
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
            self.page.goto(homepage, wait_until="domcontentloaded", timeout=30000)
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

    def previous_url(self): 
        """Get the previous URL from actual navigation history."""
        try:
            # Track all successful navigation actions, not just 'go' commands
            navigation_history = []
            
            for entry in self.command_history:
                if entry['success']:
                    # Include all navigation commands that change URL
                    if entry['command'] in ['go_to', 'go'] and entry['args']:
                        url = entry['args'][0]
                        if not url.startswith(("http://", "https://")):
                            url = "http://" + url
                        navigation_history.append({
                            'url': url,
                            'timestamp': entry['timestamp'],
                            'type': 'navigate'
                        })
                    # Also track successful back/forward navigation
                    elif entry['command'] in ['back', 'forward']:
                        # For back/forward, we need to get the current URL after the action
                        # This is more complex since we need to track actual browser state
                        try:
                            current_url = self.page.url
                            navigation_history.append({
                                'url': current_url,
                                'timestamp': entry['timestamp'], 
                                'type': entry['command']
                            })
                        except:
                            pass
            
            if len(navigation_history) < 2:
                console.print("[bold yellow][WARN][/bold yellow] No previous URL in navigation history.")
                self.log_action("previous_url", "No previous URL found", success=False)
                return None
                
            # Get the second-to-last navigation entry
            prev_entry = navigation_history[-2]
            prev_url = prev_entry['url']
            
            self.log_action("previous_url", f"Previous URL: {prev_url}", success=True)
            console.print(f"[bold cyan][INFO][/bold cyan] Previous URL: {prev_url}")
            console.print(f"[bold cyan][INFO][/bold cyan] Navigation type: {prev_entry['type']}")
            console.print(f"[bold cyan][INFO][/bold cyan] Timestamp: {prev_entry['timestamp']}")
            
            return prev_url
            
        except Exception as e:
            self.log_action("previous_url", "Failed to get previous URL", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to get previous URL: {str(e)}")
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
                    status = "✓" if entry['success'] else "✗"
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
            # Check if selector is an element ID from scan
            if hasattr(self, 'element_map') and selector in self.element_map:
                element = self.element_map[selector]
                element.click(button='right')
                console.print(f"[bold green][INFO][/bold green] Right-clicked element {selector}")
            else:
                # Use regular selector
                self.page.click(selector, button='right')
                console.print(f"[bold green][INFO][/bold green] Right-clicked element: {selector}")
            
            self.log_action("right_click", f"Selector: {selector}", success=True)
            
        except Exception as e:
            self.log_action("right_click", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to right-click {selector}: {str(e)}")

    def type_text(self, selector, text, clear_first=True):
        """Type text into an input field with human-like timing"""
        try:
            element = None
            
            # Handle numeric selectors for element_map indices
            if selector.isdigit():
                index = int(selector)
                if hasattr(self, 'element_map') and index in self.element_map:
                    element_info = self.element_map[index]
                    element = element_info["handle"]
                else:
                    console.print(f"[bold red][ERROR][/bold red] Element at index {index} not found in element_map")
                    return False
            else:
                # Try to find by label match in element_map first
                if hasattr(self, 'element_map'):
                    for idx, element_info in self.element_map.items():
                        if element_info["label"].lower() == selector.lower():
                            element = element_info["handle"]
                            break
                
                # If not found by label, try as CSS selector
                if not element:
                    element = self.page.query_selector(selector)
            
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Input element not found: {selector}")
                return False
            
            # Always clear the field first - multiple methods to ensure it's cleared
            element.click()
            self.page.wait_for_timeout(100)  # Small delay after click
            
            # Method 1: Select all and delete
            element.press('Control+a')
            self.page.wait_for_timeout(50)
            element.press('Delete')
            self.page.wait_for_timeout(50)
            
            # Method 2: Clear using fill with empty string (Playwright specific)
            element.fill('')
            self.page.wait_for_timeout(100)
            
            # Method 3: Additional clearing for stubborn fields
            current_value = element.input_value()
            if current_value:
                # If there's still content, try more aggressive clearing
                element.press('Control+a')
                element.press('Backspace')
                self.page.wait_for_timeout(50)
            
            # Verify field is cleared
            final_value = element.input_value()
            if final_value:
                console.print(f"[bold yellow][WARN][/bold yellow] Field may not be completely cleared, remaining: '{final_value}'")
            
            # Type the new text with human-like delays
            element.type(text, delay=50)  # 50ms between keystrokes
            
            console.print(f"[bold green][INFO][/bold green] Cleared and typed text into {selector}: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            self.log_action("type_text", f"Selector: {selector}, Text length: {len(text)}", success=True)
            return True
            
        except Exception as e:
            self.log_action("type_text", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to type text: {str(e)}")
            return False

    def double_click(self, selector):
        """Double-click an element by selector or element ID"""
        try:
            # Check if selector is an element ID from scan
            if hasattr(self, 'element_map') and selector in self.element_map:
                element = self.element_map[selector]
                element.dblclick()
                console.print(f"[bold green][INFO][/bold green] Double-clicked element {selector}")
            else:
                # Use regular selector
                self.page.dblclick(selector)
                console.print(f"[bold green][INFO][/bold green] Double-clicked element: {selector}")
            
            self.log_action("double_click", f"Selector: {selector}", success=True)
            
        except Exception as e:
            self.log_action("double_click", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to double-click {selector}: {str(e)}")

    def middle_click(self, selector):
        """Middle-click an element by selector or element ID"""
        try:
            # Check if selector is an element ID from scan
            if hasattr(self, 'element_map') and selector in self.element_map:
                element = self.element_map[selector]
                element.click(button='middle')
                console.print(f"[bold green][INFO][/bold green] Middle-clicked element {selector}")
            else:
                # Use regular selector
                self.page.click(selector, button='middle')
                console.print(f"[bold green][INFO][/bold green] Middle-clicked element: {selector}")
            
            self.log_action("middle_click", f"Selector: {selector}", success=True)
            
        except Exception as e:
            self.log_action("middle_click", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to middle-click {selector}: {str(e)}")


