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

class BrowserAgent:

    # INITIALIZING BROWSER AGENT 
    def __init__(self, headless=False):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        # Command and action tracking
        self.command_history: List[Dict[str, Any]] = []
        self.action_count = 0
        
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
        """Get the previous URL from command history if available."""
        try:
            # Filter command history for successful 'go' or navigation commands that changed URL
            urls = [
                entry['args'][0] for entry in self.command_history
                if entry['command'] == 'go' and entry['success']
            ]
            if len(urls) < 2:
                console.print("[bold yellow][WARN][/bold yellow] No previous URL in history.")
                self.log_action("previous_url", "No previous URL found", success=False)
                return None
            prev_url = urls[-2]
            self.log_action("previous_url", f"Previous URL: {prev_url}", success=True)
            console.print(f"[bold cyan][INFO][/bold cyan] Previous URL: {prev_url}")
            return prev_url
        except Exception as e:
            self.log_action("previous_url", "Failed to get previous URL", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to get previous URL: {str(e)}")
            return None


    def history_list(self):
        """Get the browser navigation command history."""
        try:
            console.print("\n[bold cyan]Browser Navigation History:[/bold cyan]")
            for entry in self.command_history:
                if entry['command'] == 'go':
                    status = "✓" if entry['success'] else "✗"
                    timestamp = entry['timestamp']
                    url = entry['args'][0] if entry['args'] else "N/A"
                    console.print(f"  {status} [{timestamp}] {url}")
            self.log_action("history_list", "Displayed browser history", success=True)
        except Exception as e:
            self.log_action("history_list", "Failed to display history", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to display history: {str(e)}")

    #Navigation
    def scroll(self, direction: str, amount: int = 100): #Default is 100 Pixels
        """
        Scroll the page in the specified direction by a certain amount of pixels.
        """
        try:
            direction = direction.lower()
            if direction not in ("up", "down", "left", "right"):
                raise ValueError("Direction must be one of 'up', 'down', 'left', or 'right'.")

            script_map = {
                "up": f"window.scrollBy(0, -{amount});",
                "down": f"window.scrollBy(0, {amount});",
                "left": f"window.scrollBy(-{amount}, 0);",
                "right": f"window.scrollBy({amount}, 0);"
            }

            self.page.evaluate(script_map[direction])
            self.log_action("scroll", f"Direction: {direction}, Amount: {amount}", success=True)
            console.print(f"[bold green][INFO][/bold green] Scrolled {direction} by {amount} pixels.")

        except Exception as e:
            self.log_action("scroll", f"Direction: {direction}, Amount: {amount}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll {direction}: {str(e)}")
    
    def scroll_top(self):
        """Scroll to the top of the page."""
        try:
            self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
            self.log_action("scroll_top", "Scrolled to top", success=True)
            console.print("[bold green][INFO][/bold green] Scrolled to top of the page.")
        except Exception as e:
            self.log_action("scroll_top", "Failed to scroll to top", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll to top: {str(e)}")


    def scroll_bottom(self):
        """Scroll to the bottom of the page."""
        try:
            self.page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
            self.log_action("scroll_bottom", "Scrolled to bottom", success=True)
            console.print("[bold green][INFO][/bold green] Scrolled to bottom of the page.")
        except Exception as e:
            self.log_action("scroll_bottom", "Failed to scroll to bottom", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll to bottom: {str(e)}")

    def move_to(self, x: str, y: str):
        """
        Move the mouse pointer to the specified (x, y) coordinates.
        """
        try:
            x_coord = int(x)
            y_coord = int(y)
            self.page.mouse.move(x_coord, y_coord)
            self.log_action("move_to", f"Moved mouse to ({x_coord}, {y_coord})", success=True)
            console.print(f"[bold green][INFO][/bold green] Mouse moved to ({x_coord}, {y_coord}).")
        except Exception as e:
            self.log_action("move_to", f"Failed to move mouse to ({x}, {y})", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to move mouse to ({x}, {y}): {str(e)}")

    def page_up(self): #Need to increase the magnitude
        """Scroll the page up by one page height."""
        try:
            self.page.keyboard.press("PageUp")
            self.log_action("page_up", "Scrolled page up", success=True)
            console.print("[bold green][INFO][/bold green] Page scrolled up.")
        except Exception as e:
            self.log_action("page_up", "Failed to scroll page up", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll page up: {str(e)}")


    def page_down(self): #Need to increase the magnitude
        """Scroll the page down by one page height."""
        try:
            self.page.keyboard.press("PageDown")
            self.log_action("page_down", "Scrolled page down", success=True)
            console.print("[bold green][INFO][/bold green] Page scrolled down.")
        except Exception as e:
            self.log_action("page_down", "Failed to scroll page down", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll page down: {str(e)}")

    def scroll_by(self, x: str, y: str):
        """
        Scroll the page by the specified number of pixels horizontally and vertically.
        """
        try:
            x_val = int(x)
            y_val = int(y)
            self.page.evaluate(f"window.scrollBy({x_val}, {y_val});")
            self.log_action("scroll_by", f"Scrolled by X: {x_val}px, Y: {y_val}px", success=True)
            console.print(f"[bold green][INFO][/bold green] Scrolled by X: {x_val}px, Y: {y_val}px.")
        except Exception as e:
            self.log_action("scroll_by", f"Failed to scroll by X: {x}px, Y: {y}px", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll by pixels: {str(e)}")

    def hover(self, selector: str): #Not Working
        """
        Perform mouse hover over the element matching the CSS selector.
        """
        try:
            # Wait for the element to be visible before hovering
            self.page.wait_for_selector(selector, state="visible", timeout=10000)
            self.page.hover(selector)
            self.log_action("hover", f"Hovered over selector: {selector}", success=True)
            console.print(f"[bold green][INFO][/bold green] Hovered over element matching selector: '{selector}'")
        except Exception as e:
            self.log_action("hover", f"Failed to hover over selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to hover over selector '{selector}': {str(e)}")

    def scroll_to(self, selector: str): #Scroll To
        """
        Scroll the page to the element matching the CSS selector.
        """
        try:
            # Wait for the element to be visible before scrolling
            self.page.wait_for_selector(selector, state="visible", timeout=10000)
            
            # Scroll element into view smoothly and center it vertically
            self.page.eval_on_selector(selector, "element => element.scrollIntoView({behavior: 'smooth', block: 'center'})")
            
            self.log_action("scroll_to", f"Selector: {selector}", success=True)
            console.print(f"[bold green][INFO][/bold green] Scrolled to element matching selector: '{selector}'")
        except Exception as e:
            self.log_action("scroll_to", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scroll to selector '{selector}': {str(e)}")





COMMANDS = {
    "go": BrowserAgent.go_to,
    "history": BrowserAgent.get_command_history,
    "stats": BrowserAgent.get_action_stats,
    "refresh": BrowserAgent.refresh,
    "back": BrowserAgent.back,
    "forward": BrowserAgent.forward,
    "stop": BrowserAgent.stop,
    "home": BrowserAgent.home,
    "url": BrowserAgent.url,
    "title": BrowserAgent.title,
    "previous": BrowserAgent.previous_url,
    "history": BrowserAgent.history_list,
    "scroll": BrowserAgent.scroll,
    "scroll_top": BrowserAgent.scroll_top,      
    "scroll_bottom": BrowserAgent.scroll_bottom, 
    "move": BrowserAgent.move_to,
    "page_up": BrowserAgent.page_up,
    "page_down": BrowserAgent.page_down,
    "scroll_by": BrowserAgent.scroll_by,
    "hover": BrowserAgent.hover,
    "scroll_to": BrowserAgent.scroll_to,
}


if __name__ == "__main__":

    agent = BrowserAgent(headless=False)

    try: 
        while True:
            try:
                command_line = console.input("[bold blue]Command> [/bold blue]").strip()
                if not command_line:
                    continue

                parts = parse_command(command_line)

                cmd = parts[0].lower()
                args = parts[1:]

                # Log the command attempt
                command_start_time = datetime.now()

                if cmd in ['exit', 'quit', 'q']:
                    agent.log_command(cmd, args, success=True)
                    break

                if cmd in COMMANDS:
                    try:
                        COMMANDS[cmd](agent, *args)
                        agent.log_command(cmd, args, success=True)
            
                    except Exception as e:
                        # Log command failure
                        agent.log_command(cmd, args, success=False, error=str(e))
                        print(f"Error: {e}")
                
                else:
                    console.print(f"[bold red][ERROR][/bold red] Unknown command: {cmd}")
                    agent.log_command(cmd, args, success=False, error="Unknown command")


            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit properly.[/yellow]")

            except Exception as e:
                console.print(f"[bold red][ERROR][/bold red] {str(e)}")
    
    except KeyboardInterrupt:
        console.print("\n[bold yellow][INFO][/bold yellow] Exiting...")

    finally:
        agent.close()