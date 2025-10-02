"""
Navigation mixin for browser agent.
Handles URL navigation, history, and page lifecycle.
"""

from typing import Optional
from .base_agent import console, action_logger, error_logger


class NavigationMixin:
    """
    Navigation commands for browser agent.
    Requires: self.page, self.timeout, self.log_action()
    """
    
    def go_to(self, url: str) -> bool:
        """
        Navigate to URL with automatic protocol handling.
        
        Args:
            url: Target URL (adds http:// if missing protocol)
        
        Returns:
            True if navigation succeeded, False otherwise
        """
        try:
            # Add protocol if missing
            if not url.startswith(("http://", "https://", "file://", "about:")):
                url = "https://" + url
            
            self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            
            title = self.page.title()
            self.log_action("navigate", f"{url} - {title}", success=True)
            console.print(f"[green]→[/green] {url}")
            
            return True
            
        except Exception as e:
            self.log_action("navigate", f"{url} - {str(e)}", success=False)
            console.print(f"[red]Navigation failed:[/red] {e}")
            return False
    
    def refresh(self) -> bool:
        """Reload current page."""
        try:
            current_url = self.page.url
            self.page.reload(wait_until="domcontentloaded", timeout=self.timeout)
            
            self.log_action("refresh", current_url, success=True)
            console.print(f"[green]Refreshed:[/green] {current_url}")
            return True
            
        except Exception as e:
            self.log_action("refresh", str(e), success=False)
            console.print(f"[red]Refresh failed:[/red] {e}")
            return False
    
    def back(self) -> bool:
        """Navigate backward in history."""
        try:
            response = self.page.go_back(wait_until="domcontentloaded", timeout=self.timeout)
            
            if response is None:
                console.print("[yellow]No previous page in history[/yellow]")
                self.log_action("back", "No previous page", success=False)
                return False
            
            self.log_action("back", self.page.url, success=True)
            console.print(f"[green]←[/green] {self.page.url}")
            return True
            
        except Exception as e:
            self.log_action("back", str(e), success=False)
            console.print(f"[red]Back failed:[/red] {e}")
            return False
    
    def forward(self) -> bool:
        """Navigate forward in history."""
        try:
            response = self.page.go_forward(wait_until="domcontentloaded", timeout=self.timeout)
            
            if response is None:
                console.print("[yellow]No next page in history[/yellow]")
                self.log_action("forward", "No next page", success=False)
                return False
            
            self.log_action("forward", self.page.url, success=True)
            console.print(f"[green]→[/green] {self.page.url}")
            return True
            
        except Exception as e:
            self.log_action("forward", str(e), success=False)
            console.print(f"[red]Forward failed:[/red] {e}")
            return False
    
    def home(self) -> bool:
        """Navigate to default homepage (Google)."""
        return self.go_to("https://www.google.com")
    
    def url(self) -> Optional[str]:
        """
        Get current page URL.
        
        Returns:
            Current URL string or None on error
        """
        try:
            current_url = self.page.url
            console.print(f"[cyan]URL:[/cyan] {current_url}")
            self.log_action("url", current_url, success=True)
            return current_url
            
        except Exception as e:
            console.print(f"[red]Failed to get URL:[/red] {e}")
            self.log_action("url", str(e), success=False)
            return None
    
    def title(self) -> Optional[str]:
        """
        Get current page title.
        
        Returns:
            Page title string or None on error
        """
        try:
            page_title = self.page.title()
            console.print(f"[cyan]Title:[/cyan] {page_title}")
            self.log_action("title", page_title, success=True)
            return page_title
            
        except Exception as e:
            console.print(f"[red]Failed to get title:[/red] {e}")
            self.log_action("title", str(e), success=False)
            return None
    
    def history_list(self) -> bool:
        """
        Display complete navigation history from command log.
        Shows all go/back/forward/home/refresh actions.
        
        Returns:
            True if history displayed, False if empty
        """
        try:
            nav_commands = ['go', 'go_to', 'back', 'forward', 'home', 'refresh']
            
            nav_entries = [
                entry for entry in self.command_history 
                if entry['command'] in nav_commands
            ]
            
            if not nav_entries:
                console.print("[yellow]No navigation history yet[/yellow]")
                return False
            
            console.print("\n[bold cyan]Navigation History:[/bold cyan]")
            console.print("─" * 80)
            
            for entry in nav_entries:
                # Format timestamp (just HH:MM:SS)
                timestamp = entry['timestamp'].split('T')[1].split('.')[0]
                
                # Status indicator
                status = "+" if entry['success'] else "x"
                color = "green" if entry['success'] else "red"
                
                # Action description
                if entry['command'] in ['go', 'go_to'] and entry['args']:
                    url = entry['args'][0]
                    if not url.startswith(("http://", "https://")):
                        url = "https://" + url
                    action = f"Navigate → {url}"
                elif entry['command'] == 'back':
                    action = "Back ←"
                elif entry['command'] == 'forward':
                    action = "Forward →"
                elif entry['command'] == 'home':
                    action = "Home → https://www.google.com"
                elif entry['command'] == 'refresh':
                    action = "Refresh ↻"
                else:
                    action = entry['command']
                
                console.print(f"[{color}]{status}[/{color}] [{timestamp}] {action}")
            
            console.print("─" * 80)
            console.print(f"[cyan]Total:[/cyan] {len(nav_entries)} navigation actions\n")
            
            self.log_action("history_list", f"{len(nav_entries)} entries", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to display history:[/red] {e}")
            self.log_action("history_list", str(e), success=False)
            return False
    
    def wait_for_load(self, timeout: Optional[int] = None) -> bool:
        """
        Wait for page to finish loading (network idle).
        
        Args:
            timeout: Override default timeout (ms)
        
        Returns:
            True if page loaded, False on timeout
        """
        try:
            wait_time = timeout or self.timeout
            self.page.wait_for_load_state('networkidle', timeout=wait_time)
            
            console.print(f"[green]Page loaded[/green]")
            self.log_action("wait_for_load", f"{wait_time}ms", success=True)
            return True
            
        except Exception as e:
            console.print(f"[yellow]Load timeout:[/yellow] {e}")
            self.log_action("wait_for_load", str(e), success=False)
            return False