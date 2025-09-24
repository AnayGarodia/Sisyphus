from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
from rich.logging import RichHandler
import logging
import shlex
from typing import Optional, List

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

    def get_command_history(self, limit: int = 10):
        """Get recent command history"""
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

                try:
                    if cmd in ['exit', 'quit', 'q']:
                        agent.log_command(cmd, args, success=True)
                        break

                    elif cmd == 'go' and args:
                        agent.go_to(args[0])
                        agent.log_command(cmd, args, success=True)

                    elif cmd == 'history':
                        limit = int(args[0]) if args and args[0].isdigit() else 10
                        agent.get_command_history(limit)
                        agent.log_command(cmd, args, success=True)

                    elif cmd == 'stats':
                        agent.get_action_stats()
                        agent.log_command(cmd, args, success=True)
                        
                    else:
                        error_msg = f"Unknown command: {cmd}"
                        agent.log_command(cmd, args, success=False, error=error_msg)
                        console.print(f"[bold red][ERROR][/bold red] {error_msg}")

                except Exception as e:
                    # Log command failure
                    agent.log_command(cmd, args, success=False, error=str(e))
                    raise
                


            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit properly.[/yellow]")

            except Exception as e:
                console.print(f"[bold red][ERROR][/bold red] {str(e)}")
    
    except KeyboardInterrupt:
        console.print("\n[bold yellow][INFO][/bold yellow] Exiting...")

    finally:
        agent.close()