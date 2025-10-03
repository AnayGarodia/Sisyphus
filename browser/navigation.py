"""
Advanced navigation mixin for browser agent.
Handles URL navigation, history, page lifecycle, and smart waiting.
"""

from typing import Optional, Dict, List, Literal
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
from .base_agent import console, action_logger, error_logger


class NavigationMixin:
    """
    Advanced navigation commands for browser agent.
    Requires: self.page, self.timeout, self.log_action()
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._navigation_stack = []  # Track navigation for better history
        self._page_load_metrics = {}
        self.default_homepage = "https://www.google.com"
    
    def go_to(self, url: str, wait_strategy: str = "smart", force_reload: bool = False) -> bool:
        """
        Navigate to URL with intelligent protocol handling and validation.
        
        Args:
            url: Target URL (adds https:// if missing)
            wait_strategy: 'smart', 'load', 'domcontentloaded', 'networkidle', or 'commit'
            force_reload: Force reload if already on this URL
        
        Returns:
            True if navigation succeeded
        """
        try:
            start_time = time.time()
            
            # Smart URL processing
            processed_url = self._process_url(url)
            
            if not processed_url:
                console.print(f"[red]Invalid URL:[/red] {url}")
                self.log_action("navigate", f"Invalid: {url}", success=False)
                return False
            
            # Check if already on this page
            current_url = self.page.url
            if not force_reload and self._urls_match(current_url, processed_url):
                console.print(f"[yellow]Already on:[/yellow] {processed_url}")
                console.print("[dim]Use force_reload=True to reload anyway[/dim]")
                return True
            
            # Determine wait strategy
            if wait_strategy == "smart":
                wait_until = self._determine_wait_strategy(processed_url)
            else:
                wait_until = wait_strategy
            
            # Navigate with timeout handling
            console.print(f"[cyan]Navigating to:[/cyan] {processed_url}")
            console.print(f"[dim]Wait strategy: {wait_until}[/dim]")
            
            try:
                response = self.page.goto(
                    processed_url,
                    wait_until=wait_until,
                    timeout=self.timeout
                )
                
                # Check response status
                if response:
                    status = response.status
                    if status >= 400:
                        console.print(f"[yellow]HTTP {status}:[/yellow] Page loaded with error status")
                
            except Exception as nav_error:
                # Try fallback strategy if smart/networkidle fails
                if wait_until in ["networkidle", "load"]:
                    console.print(f"[yellow]Timeout with {wait_until}, trying domcontentloaded...[/yellow]")
                    response = self.page.goto(
                        processed_url,
                        wait_until="domcontentloaded",
                        timeout=self.timeout
                    )
                else:
                    raise
            
            # Get page info
            title = self._safe_get_title()
            load_time = time.time() - start_time
            
            # Store metrics
            self._page_load_metrics[processed_url] = {
                'load_time': load_time,
                'strategy': wait_until,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update navigation stack
            self._navigation_stack.append({
                'url': processed_url,
                'title': title,
                'timestamp': datetime.now().isoformat()
            })
            
            # Display results
            console.print(f"[green]✓ Loaded:[/green] {title or processed_url}")
            console.print(f"[dim]Time: {load_time:.2f}s | URL: {self.page.url}[/dim]")
            
            self.log_action("navigate", f"{processed_url} [{load_time:.2f}s]", success=True)
            return True
            
        except Exception as e:
            error_msg = str(e)
            console.print(f"[red]Navigation failed:[/red] {error_msg}")
            
            # Provide helpful suggestions
            if "timeout" in error_msg.lower():
                console.print("[dim]Tip: Page might be slow. Try increasing timeout or using wait_strategy='commit'[/dim]")
            elif "net::" in error_msg.lower() or "DNS" in error_msg:
                console.print("[dim]Tip: Check URL spelling and internet connection[/dim]")
            
            self.log_action("navigate", f"{url} - {error_msg}", success=False)
            return False
    
    def _process_url(self, url: str) -> Optional[str]:
        """Process and validate URL with smart handling."""
        if not url or not url.strip():
            return None
        
        url = url.strip()
        
        # Handle special URLs
        if url.startswith(("about:", "file://", "data:")):
            return url
        
        # Handle relative URLs (if we're on a page)
        if url.startswith(("/", "./")):
            try:
                base_url = self.page.url
                return urljoin(base_url, url)
            except:
                return None
        
        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            # Check for common patterns
            if url.startswith("localhost") or url.startswith("127.0.0.1"):
                url = "http://" + url
            else:
                url = "https://" + url
        
        # Validate
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return None
            return url
        except:
            return None
    
    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs are effectively the same."""
        try:
            p1 = urlparse(url1)
            p2 = urlparse(url2)
            
            # Compare normalized versions
            return (
                p1.scheme == p2.scheme and
                p1.netloc.lower() == p2.netloc.lower() and
                p1.path.rstrip('/') == p2.path.rstrip('/')
            )
        except:
            return url1 == url2
    
    def _determine_wait_strategy(self, url: str) -> str:
        """Intelligently determine best wait strategy for URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Single Page Apps (SPAs) - use networkidle
        spa_domains = ['github.com', 'gmail.com', 'twitter.com', 'x.com', 
                      'reddit.com', 'discord.com', 'notion.so']
        if any(spa in domain for spa in spa_domains):
            return "networkidle"
        
        # News/content sites - domcontentloaded is usually enough
        content_domains = ['wikipedia.org', 'stackoverflow.com', 'medium.com']
        if any(content in domain for content in content_domains):
            return "domcontentloaded"
        
        # Default: load (good balance)
        return "load"
    
    def _safe_get_title(self) -> str:
        """Safely get page title with fallback."""
        try:
            title = self.page.title()
            return title if title else "Untitled"
        except:
            return "Untitled"
    
    def go(self, url: str) -> bool:
        """Alias for go_to() - shorter command."""
        return self.go_to(url)
    
    def visit(self, url: str) -> bool:
        """Alias for go_to() - more intuitive name."""
        return self.go_to(url)
    
    def open(self, url: str) -> bool:
        """Alias for go_to() - common terminology."""
        return self.go_to(url)
    
    def refresh(self, hard: bool = False) -> bool:
        """
        Reload current page.
        
        Args:
            hard: If True, bypass cache (Ctrl+Shift+R equivalent)
        
        Returns:
            True if refresh succeeded
        """
        try:
            current_url = self.page.url
            
            if hard:
                # Hard reload: bypass cache
                console.print("[cyan]Hard refresh (bypassing cache)...[/cyan]")
                self.page.reload(wait_until="domcontentloaded", timeout=self.timeout)
                # Clear browser cache for this page
                self.page.evaluate("() => { location.reload(true); }")
            else:
                self.page.reload(wait_until="domcontentloaded", timeout=self.timeout)
            
            self.log_action("refresh", f"{current_url} [hard={hard}]", success=True)
            console.print(f"[green]✓ Refreshed:[/green] {current_url}")
            return True
            
        except Exception as e:
            self.log_action("refresh", str(e), success=False)
            console.print(f"[red]Refresh failed:[/red] {e}")
            return False
    
    def reload(self) -> bool:
        """Alias for refresh()."""
        return self.refresh()
    
    def back(self, steps: int = 1) -> bool:
        """
        Navigate backward in history.
        
        Args:
            steps: Number of steps to go back (default: 1)
        
        Returns:
            True if navigation succeeded
        """
        try:
            if steps < 1:
                console.print("[yellow]Steps must be >= 1[/yellow]")
                return False
            
            # Navigate back N times
            for i in range(steps):
                response = self.page.go_back(
                    wait_until="domcontentloaded",
                    timeout=self.timeout
                )
                
                if response is None:
                    if i == 0:
                        console.print("[yellow]No previous page in history[/yellow]")
                        self.log_action("back", "No previous page", success=False)
                        return False
                    else:
                        console.print(f"[yellow]Went back {i} step(s) (no more history)[/yellow]")
                        break
                
                # Small delay between multiple steps
                if steps > 1 and i < steps - 1:
                    time.sleep(0.3)
            
            current_url = self.page.url
            title = self._safe_get_title()
            
            steps_text = f"{steps} step{'s' if steps > 1 else ''}"
            self.log_action("back", f"{steps_text} -> {current_url}", success=True)
            console.print(f"[green]← Back ({steps_text}):[/green] {title}")
            console.print(f"[dim]{current_url}[/dim]")
            return True
            
        except Exception as e:
            self.log_action("back", str(e), success=False)
            console.print(f"[red]Back failed:[/red] {e}")
            return False
    
    def forward(self, steps: int = 1) -> bool:
        """
        Navigate forward in history.
        
        Args:
            steps: Number of steps to go forward (default: 1)
        
        Returns:
            True if navigation succeeded
        """
        try:
            if steps < 1:
                console.print("[yellow]Steps must be >= 1[/yellow]")
                return False
            
            # Navigate forward N times
            for i in range(steps):
                response = self.page.go_forward(
                    wait_until="domcontentloaded",
                    timeout=self.timeout
                )
                
                if response is None:
                    if i == 0:
                        console.print("[yellow]No next page in history[/yellow]")
                        self.log_action("forward", "No next page", success=False)
                        return False
                    else:
                        console.print(f"[yellow]Went forward {i} step(s) (no more history)[/yellow]")
                        break
                
                # Small delay between multiple steps
                if steps > 1 and i < steps - 1:
                    time.sleep(0.3)
            
            current_url = self.page.url
            title = self._safe_get_title()
            
            steps_text = f"{steps} step{'s' if steps > 1 else ''}"
            self.log_action("forward", f"{steps_text} -> {current_url}", success=True)
            console.print(f"[green]→ Forward ({steps_text}):[/green] {title}")
            console.print(f"[dim]{current_url}[/dim]")
            return True
            
        except Exception as e:
            self.log_action("forward", str(e), success=False)
            console.print(f"[red]Forward failed:[/red] {e}")
            return False
    
    def home(self, url: Optional[str] = None) -> bool:
        """
        Navigate to homepage.
        
        Args:
            url: Custom homepage (if provided, sets as default)
        
        Returns:
            True if navigation succeeded
        """
        if url:
            # Set new default homepage
            self.default_homepage = url
            console.print(f"[cyan]Homepage set to:[/cyan] {url}")
        
        return self.go_to(self.default_homepage)
    
    def url(self, copy: bool = False) -> Optional[str]:
        """
        Get current page URL.
        
        Args:
            copy: If True, copy to clipboard (requires pyperclip)
        
        Returns:
            Current URL or None on error
        """
        try:
            current_url = self.page.url
            console.print(f"[cyan]URL:[/cyan] {current_url}")
            
            if copy:
                try:
                    import pyperclip
                    pyperclip.copy(current_url)
                    console.print("[green]✓ Copied to clipboard[/green]")
                except ImportError:
                    console.print("[dim]Install pyperclip to enable clipboard copy[/dim]")
            
            self.log_action("url", current_url, success=True)
            return current_url
            
        except Exception as e:
            console.print(f"[red]Failed to get URL:[/red] {e}")
            self.log_action("url", str(e), success=False)
            return None
    
    def title(self, full: bool = False) -> Optional[str]:
        """
        Get current page title.
        
        Args:
            full: If True, also show URL and meta description
        
        Returns:
            Page title or None on error
        """
        try:
            page_title = self._safe_get_title()
            console.print(f"[cyan]Title:[/cyan] {page_title}")
            
            if full:
                # Show additional page info
                url = self.page.url
                console.print(f"[dim]URL: {url}[/dim]")
                
                try:
                    meta_desc = self.page.evaluate("""
                        () => {
                            const meta = document.querySelector('meta[name="description"]');
                            return meta ? meta.content : null;
                        }
                    """)
                    if meta_desc:
                        console.print(f"[dim]Description: {meta_desc[:100]}...[/dim]")
                except:
                    pass
            
            self.log_action("title", page_title, success=True)
            return page_title
            
        except Exception as e:
            console.print(f"[red]Failed to get title:[/red] {e}")
            self.log_action("title", str(e), success=False)
            return None
    
    def history(self, limit: Optional[int] = 20, filter_type: Optional[str] = None) -> bool:
        """
        Display enhanced navigation history.
        
        Args:
            limit: Maximum entries to show (most recent first)
            filter_type: Filter by type ('navigate', 'back', 'forward', 'refresh')
        
        Returns:
            True if history displayed
        """
        try:
            nav_commands = ['go', 'go_to', 'navigate', 'visit', 'open', 'back', 'forward', 'home', 'refresh', 'reload']
            
            nav_entries = [
                entry for entry in self.command_history
                if entry['command'] in nav_commands
            ]
            
            # Apply filter
            if filter_type:
                filter_commands = {
                    'navigate': ['go', 'go_to', 'navigate', 'visit', 'open', 'home'],
                    'back': ['back'],
                    'forward': ['forward'],
                    'refresh': ['refresh', 'reload']
                }
                if filter_type in filter_commands:
                    nav_entries = [
                        e for e in nav_entries 
                        if e['command'] in filter_commands[filter_type]
                    ]
            
            if not nav_entries:
                console.print("[yellow]No navigation history yet[/yellow]")
                return False
            
            # Apply limit (most recent first)
            if limit is not None:
                nav_entries = nav_entries[-limit:]
            
            filter_text = f" ({filter_type})" if filter_type else ""
            console.print(f"\n[bold cyan]Navigation History{filter_text}:[/bold cyan]")
            console.print("─" * 90)
            
            for entry in reversed(nav_entries):  # Most recent first
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(entry['timestamp'])
                    timestamp = dt.strftime("%H:%M:%S")
                except:
                    timestamp = entry['timestamp'].split('T')[1].split('.')[0]
                
                # Status indicator
                status = "✓" if entry['success'] else "✗"
                color = "green" if entry['success'] else "red"
                
                # Action description
                cmd = entry['command']
                args = entry.get('args', [])
                
                if cmd in ['go', 'go_to', 'navigate', 'visit', 'open'] and args:
                    url = args[0]
                    if not url.startswith(("http://", "https://")):
                        url = "https://" + url
                    action = f"→ {url}"
                elif cmd == 'back':
                    action = "← Back"
                    if args and args[0] > 1:
                        action += f" ({args[0]} steps)"
                elif cmd == 'forward':
                    action = "→ Forward"
                    if args and args[0] > 1:
                        action += f" ({args[0]} steps)"
                elif cmd == 'home':
                    homepage = self.default_homepage
                    action = f"⌂ Home → {homepage}"
                elif cmd in ['refresh', 'reload']:
                    action = "↻ Refresh"
                else:
                    action = cmd
                
                console.print(f"[{color}]{status}[/{color}] [{timestamp}] {action}")
            
            console.print("─" * 90)
            console.print(f"[cyan]Total:[/cyan] {len(nav_entries)} navigation actions")
            
            if not filter_type:
                console.print("[dim]Tip: Use filter_type='navigate'|'back'|'forward'|'refresh' to filter[/dim]\n")
            
            self.log_action("history", f"{len(nav_entries)} entries", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to display history:[/red] {e}")
            error_logger.debug(f"History error: {e}")
            self.log_action("history", str(e), success=False)
            return False
    
    def history_list(self, limit: Optional[int] = None) -> bool:
        """Alias for history() for backward compatibility."""
        return self.history(limit=limit)
    
    def nav_stack(self, limit: int = 10) -> bool:
        """
        Show navigation stack (pages visited in current session).
        
        Args:
            limit: Maximum entries to show
        
        Returns:
            True if stack displayed
        """
        if not self._navigation_stack:
            console.print("[yellow]Navigation stack is empty[/yellow]")
            return False
        
        console.print(f"\n[bold cyan]Navigation Stack:[/bold cyan]")
        console.print("─" * 90)
        
        stack = self._navigation_stack[-limit:] if limit else self._navigation_stack
        
        for i, entry in enumerate(reversed(stack), 1):
            try:
                dt = datetime.fromisoformat(entry['timestamp'])
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = entry['timestamp'][:8]
            
            title = entry['title'][:50] + "..." if len(entry['title']) > 50 else entry['title']
            url = entry['url']
            
            marker = "→" if i == 1 else " "
            console.print(f"{marker} [{time_str}] {title}")
            console.print(f"  [dim]{url}[/dim]")
        
        console.print("─" * 90)
        console.print(f"[cyan]Total:[/cyan] {len(self._navigation_stack)} pages in session\n")
        
        return True
    
    def wait_for_load(
        self, 
        timeout: Optional[int] = None,
        strategy: Literal["networkidle", "load", "domcontentloaded", "commit"] = "load"
    ) -> bool:
        """
        Wait for page to finish loading.
        
        Args:
            timeout: Custom timeout in ms (overrides default)
            strategy: Wait strategy:
                - 'networkidle': Wait until network is idle (no requests for 500ms)
                - 'load': Wait for load event (default)
                - 'domcontentloaded': Wait for DOMContentLoaded event
                - 'commit': Wait for navigation to commit (fastest)
        
        Returns:
            True if page loaded successfully
        """
        try:
            wait_time = timeout or self.timeout
            
            console.print(f"[cyan]Waiting for page load...[/cyan] [dim]({strategy})[/dim]")
            
            self.page.wait_for_load_state(strategy, timeout=wait_time)
            
            console.print(f"[green]✓ Page loaded[/green] [dim](strategy={strategy})[/dim]")
            self.log_action("wait_for_load", f"{wait_time}ms [{strategy}]", success=True)
            return True
            
        except Exception as e:
            console.print(f"[yellow]Load timeout:[/yellow] {e}")
            console.print("[dim]Tip: Try a different strategy: 'commit', 'domcontentloaded', or increase timeout[/dim]")
            self.log_action("wait_for_load", str(e), success=False)
            return False
    
    def wait_for(
        self, 
        selector: Optional[str] = None,
        url_pattern: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Advanced wait for specific conditions.
        
        Args:
            selector: CSS selector to wait for
            url_pattern: URL pattern to wait for
            timeout: Custom timeout in ms
        
        Returns:
            True if condition met
        """
        try:
            wait_time = timeout or self.timeout
            
            if selector:
                console.print(f"[cyan]Waiting for element:[/cyan] {selector}")
                self.page.wait_for_selector(selector, timeout=wait_time)
                console.print(f"[green]✓ Element appeared[/green]")
                self.log_action("wait_for", f"selector: {selector}", success=True)
                return True
            
            elif url_pattern:
                console.print(f"[cyan]Waiting for URL:[/cyan] {url_pattern}")
                self.page.wait_for_url(url_pattern, timeout=wait_time)
                console.print(f"[green]✓ URL matched[/green]")
                self.log_action("wait_for", f"url: {url_pattern}", success=True)
                return True
            
            else:
                console.print("[yellow]Specify either selector or url_pattern[/yellow]")
                return False
                
        except Exception as e:
            console.print(f"[yellow]Wait timeout:[/yellow] {e}")
            self.log_action("wait_for", str(e), success=False)
            return False
    
    def page_info(self) -> Dict:
        """
        Get comprehensive page information.
        
        Returns:
            Dictionary with page metadata
        """
        try:
            info = {
                'url': self.page.url,
                'title': self._safe_get_title(),
                'load_time': None,
                'timestamp': datetime.now().isoformat()
            }
            
            # Get load time if available
            url = self.page.url
            if url in self._page_load_metrics:
                info['load_time'] = self._page_load_metrics[url]['load_time']
            
            # Get additional metadata
            try:
                meta = self.page.evaluate("""
                    () => ({
                        description: document.querySelector('meta[name="description"]')?.content,
                        keywords: document.querySelector('meta[name="keywords"]')?.content,
                        author: document.querySelector('meta[name="author"]')?.content,
                        viewport: document.querySelector('meta[name="viewport"]')?.content,
                        charset: document.characterSet,
                        lang: document.documentElement.lang,
                        links: document.querySelectorAll('a').length,
                        images: document.querySelectorAll('img').length,
                        scripts: document.querySelectorAll('script').length
                    })
                """)
                info.update(meta)
            except:
                pass
            
            # Display
            console.print("\n[bold cyan]Page Information:[/bold cyan]")
            console.print("─" * 70)
            console.print(f"  [bold]Title:[/bold] {info['title']}")
            console.print(f"  [bold]URL:[/bold] {info['url']}")
            
            if info.get('description'):
                desc = info['description'][:100] + "..." if len(info['description']) > 100 else info['description']
                console.print(f"  [bold]Description:[/bold] {desc}")
            
            if info.get('load_time'):
                console.print(f"  [bold]Load Time:[/bold] {info['load_time']:.2f}s")
            
            if info.get('lang'):
                console.print(f"  [bold]Language:[/bold] {info['lang']}")
            
            if info.get('links'):
                console.print(f"  [bold]Links:[/bold] {info['links']}")
            
            if info.get('images'):
                console.print(f"  [bold]Images:[/bold] {info['images']}")
            
            console.print("─" * 70 + "\n")
            
            self.log_action("page_info", info['url'], success=True)
            return info
            
        except Exception as e:
            console.print(f"[red]Failed to get page info:[/red] {e}")
            self.log_action("page_info", str(e), success=False)
            return {}