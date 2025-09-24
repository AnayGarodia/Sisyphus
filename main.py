from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import shlex
import re

console = Console()

class BrowserAgent:
    def __init__(self, headless=False):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        console.print("[bold green][INFO][/bold green] Browser started. Type 'help' for commands.")

    # ------------------- Core Navigation -------------------
    def go_to(self, url: str):
        """Navigate to a URL with better error handling."""
        try:
            # Fix common URL typos
            url = url.replace(',', '.')
            if not url.startswith("http"):
                url = "https://" + url
            
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            console.print(f"[bold green][INFO][/bold green] Navigated to {url}")
            console.print(f"[dim]Page title: {self.page.title()}[/dim]")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Failed to navigate: {str(e)}")

    def back(self):
        """Go back in browser history."""
        try:
            self.page.go_back(wait_until="domcontentloaded")
            console.print("[bold green][INFO][/bold green] Navigated back")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Cannot go back: {str(e)}")

    def forward(self):
        """Go forward in browser history."""
        try:
            self.page.go_forward(wait_until="domcontentloaded")
            console.print("[bold green][INFO][/bold green] Navigated forward")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Cannot go forward: {str(e)}")

    def refresh(self):
        """Reload the current page."""
        try:
            self.page.reload(wait_until="domcontentloaded")
            console.print("[bold green][INFO][/bold green] Page refreshed")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Failed to refresh: {str(e)}")

    # ------------------- Smart Element Interaction -------------------
    def smart_click(self, text_or_selector: str):
        """Click by text content, selector, or smart matching."""
        try:
            # Try clicking by text content first
            if self._try_click_by_text(text_or_selector):
                return
            
            # Try as CSS selector
            if self._try_click_by_selector(text_or_selector):
                return
                
            console.print(f"[bold red][ERROR][/bold red] Could not find clickable element: {text_or_selector}")
            
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Click failed: {str(e)}")

    def _try_click_by_text(self, text: str) -> bool:
        """Try to click by text content."""
        try:
            # Try exact text match
            locator = self.page.get_by_text(text, exact=True)
            if locator.count() > 0:
                locator.first.click(timeout=5000)
                console.print(f"[bold green][INFO][/bold green] Clicked element with text: '{text}'")
                return True
                
            # Try partial text match
            locator = self.page.get_by_text(text)
            if locator.count() > 0:
                locator.first.click(timeout=5000)
                console.print(f"[bold green][INFO][/bold green] Clicked element containing text: '{text}'")
                return True
                
            # Try role-based matching for buttons/links
            for role in ['button', 'link']:
                locator = self.page.get_by_role(role, name=re.compile(text, re.IGNORECASE))
                if locator.count() > 0:
                    locator.first.click(timeout=5000)
                    console.print(f"[bold green][INFO][/bold green] Clicked {role} with name: '{text}'")
                    return True
                    
        except PlaywrightTimeoutError:
            pass
        return False

    def _try_click_by_selector(self, selector: str) -> bool:
        """Try to click by CSS selector."""
        try:
            locator = self.page.locator(selector)
            if locator.count() > 0:
                locator.first.click(timeout=5000)
                console.print(f"[bold green][INFO][/bold green] Clicked element: {selector}")
                return True
        except PlaywrightTimeoutError:
            pass
        return False

    def fill_form(self, field_label: str, text: str):
        """Fill form field by label or placeholder."""
        try:
            # Try by label
            locator = self.page.get_by_label(field_label)
            if locator.count() > 0:
                locator.fill(text)
                console.print(f"[bold green][INFO][/bold green] Filled field '{field_label}' with '{text}'")
                return
                
            # Try by placeholder
            locator = self.page.get_by_placeholder(field_label)
            if locator.count() > 0:
                locator.fill(text)
                console.print(f"[bold green][INFO][/bold green] Filled field with placeholder '{field_label}'")
                return
                
            console.print(f"[bold red][ERROR][/bold red] Could not find form field: {field_label}")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Fill failed: {str(e)}")

    # ------------------- Enhanced Page Inspection -------------------
    def search_text(self, query: str, limit: int = 10):
        """Search for text on the page."""
        try:
            elements = self.page.locator(f"text={query}").all()
            if not elements:
                elements = self.page.locator(f"*:has-text('{query}')").all()
                
            if elements:
                table = Table(title=f"Found {min(len(elements), limit)} elements containing '{query}'")
                table.add_column("Index", justify="right")
                table.add_column("Tag")
                table.add_column("Text", overflow="fold")
                
                for i, el in enumerate(elements[:limit]):
                    tag_name = el.evaluate("el => el.tagName")
                    text = el.inner_text()[:150]
                    table.add_row(str(i), tag_name, text)
                console.print(table)
            else:
                console.print(f"[yellow]No elements found containing '{query}'[/yellow]")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Search failed: {str(e)}")

    def list_interactive(self, limit: int = 20):
        """List interactive elements (buttons, links, inputs)."""
        try:
            table = Table(title="Interactive Elements")
            table.add_column("Index", justify="right")
            table.add_column("Type")
            table.add_column("Text/Value", overflow="fold")
            table.add_column("Selector", overflow="fold")
            
            count = 0
            # Get buttons
            for btn in self.page.locator("button, input[type='button'], input[type='submit']").all()[:limit//3]:
                text = btn.inner_text() or btn.get_attribute("value") or ""
                selector = f"button:nth-child({count+1})"
                table.add_row(str(count), "Button", text[:50], selector)
                count += 1
                
            # Get links  
            for link in self.page.locator("a[href]").all()[:limit//3]:
                text = link.inner_text()[:50]
                href = link.get_attribute("href")
                table.add_row(str(count), "Link", text, href[:50])
                count += 1
                
            # Get inputs
            for inp in self.page.locator("input, textarea, select").all()[:limit//3]:
                input_type = inp.get_attribute("type") or "text"
                placeholder = inp.get_attribute("placeholder") or ""
                table.add_row(str(count), f"Input ({input_type})", placeholder[:50], "")
                count += 1
                
            console.print(table)
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Failed to list elements: {str(e)}")

    def get_page_info(self):
        """Get current page information."""
        try:
            info = Panel.fit(
                f"[bold]URL:[/bold] {self.page.url}\n"
                f"[bold]Title:[/bold] {self.page.title()}\n"
                f"[bold]Status:[/bold] Ready",
                title="Page Information",
                border_style="blue"
            )
            console.print(info)
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Failed to get page info: {str(e)}")

    # ------------------- Utility -------------------
    def screenshot(self, path: str = "screenshot.png"):
        """Take a screenshot."""
        try:
            self.page.screenshot(path=path, full_page=True)
            console.print(f"[bold green][INFO][/bold green] Screenshot saved to {path}")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Screenshot failed: {str(e)}")

    def wait_for(self, text_or_selector: str, timeout: int = 10000):
        """Wait for an element to appear."""
        try:
            # Try waiting for text
            try:
                self.page.wait_for_selector(f"text={text_or_selector}", timeout=timeout)
                console.print(f"[bold green][INFO][/bold green] Found text: {text_or_selector}")
                return
            except:
                pass
                
            # Try waiting for selector
            self.page.wait_for_selector(text_or_selector, timeout=timeout)
            console.print(f"[bold green][INFO][/bold green] Found element: {text_or_selector}")
        except PlaywrightTimeoutError:
            console.print(f"[bold red][ERROR][/bold red] Timeout waiting for: {text_or_selector}")

    def help(self):
        """Show help information."""
        help_text = """[bold cyan]Available Commands:[/bold cyan]

[bold]Navigation:[/bold]
  go_to <url>              Navigate to URL
  back                     Go back in history  
  forward                  Go forward in history
  refresh                  Reload current page

[bold]Interaction:[/bold]
  click <text_or_selector> Smart click by text or selector
  fill <label> <text>      Fill form field by label
  wait <text_or_selector>  Wait for element to appear

[bold]Inspection:[/bold]
  info                     Show current page info
  search <text>            Search for text on page
  interactive              List clickable elements
  screenshot [path]        Take screenshot

[bold]Utility:[/bold]
  help                     Show this help
  exit                     Close browser and exit

[bold]Examples:[/bold]
  click "Sign in"
  fill "username" john@example.com
  search "login"
"""
        console.print(Panel(help_text, title="Help", border_style="green"))

    def close(self):
        """Close browser and cleanup."""
        try:
            self.context.close()
            self.browser.close()
            self.playwright.stop()
            console.print("[bold green][INFO][/bold green] Browser closed.")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Error closing browser: {str(e)}")


def parse_command(command_line: str):
    """Parse command line with proper quote handling."""
    try:
        return shlex.split(command_line)
    except ValueError:
        # Fallback for malformed quotes
        return command_line.split()


if __name__ == "__main__":
    agent = BrowserAgent(headless=False)
    
    try:
        while True:
            try:
                command_line = console.input("[bold cyan]> [/bold cyan]").strip()
                if not command_line:
                    continue
                    
                parts = parse_command(command_line)
                cmd = parts[0].lower()
                args = parts[1:]

                # Navigation commands
                if cmd == "go_to" and args:
                    agent.go_to(args[0])
                elif cmd == "back":
                    agent.back()
                elif cmd == "forward":
                    agent.forward()  
                elif cmd == "refresh":
                    agent.refresh()
                    
                # Interaction commands
                elif cmd == "click" and args:
                    agent.smart_click(" ".join(args))
                elif cmd == "fill" and len(args) >= 2:
                    agent.fill_form(args[0], " ".join(args[1:]))
                elif cmd == "wait" and args:
                    agent.wait_for(" ".join(args))
                    
                # Inspection commands
                elif cmd == "info":
                    agent.get_page_info()
                elif cmd == "search" and args:
                    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
                    agent.search_text(args[0], limit)
                elif cmd == "interactive":
                    limit = int(args[0]) if args and args[0].isdigit() else 20
                    agent.list_interactive(limit)
                elif cmd == "screenshot":
                    path = args[0] if args else "screenshot.png"
                    agent.screenshot(path)
                    
                # Utility commands
                elif cmd == "help":
                    agent.help()
                elif cmd in ["exit", "quit", "q"]:
                    break
                else:
                    console.print(f"[bold red][ERROR][/bold red] Unknown command: {cmd}. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit properly.[/yellow]")
            except Exception as e:
                console.print(f"[bold red][ERROR][/bold red] Command error: {str(e)}")
                
    except KeyboardInterrupt:
        console.print("\n[bold yellow][INFO][/bold yellow] Exiting...")
    finally:
        agent.close()