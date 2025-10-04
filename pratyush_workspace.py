#!/usr/bin/env python3
"""
Anay's experimental workspace.
Full REPL with all standard commands PLUS experimental features.
"""

from main import BrowserAgent, run_repl
from browser import console
from commands import build_command_registry
import sys


class ExperimentalAgent(BrowserAgent):
    """
    Extends the standard BrowserAgent with experimental features.
    Inherits ALL standard functionality + adds your test features.
    """
    
        
    def wiki_test(self, search_term="Python programming language"):
        """
        Simple test: Navigate to Wikipedia and search.
        Usage: wiki_test "search term"
        """
        console.print(f"[yellow]Testing Wikipedia navigation with: {search_term}[/yellow]")
        
        try:
            # Go to Wikipedia
            self.go_to("wikipedia.org")
            console.print("[green]Step 1: Navigated to Wikipedia[/green]")
            
            # Wait a moment for page to load
            self.wait_for_load()
            console.print("[green]Step 2: Page loaded[/green]")
            
            # Scan for inputs
            self.scan("inputs")
            console.print("[green]Step 3: Scanned page[/green]")
            
            # Type in search box (usually element 1)
            self.type(1, search_term)
            console.print(f"[green]Step 4: Typed '{search_term}'[/green]")
            
            # Press Enter to search
            self.press_key("Enter")
            console.print("[green]Step 5: Pressed Enter[/green]")
            
            # Wait for results
            self.wait_for_load()
            console.print("[green]Test complete![/green]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Test failed:[/red] {e}")
            return False

    def screenshot(self, filename: str = None):
        """
        Take a full page screenshot.
        Usage: screenshot [filename]
        """
        try:
            import os
            import re
            from datetime import datetime
            from urllib.parse import urlparse
            
            # Create screenshots folder if it doesn't exist
            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
            
            # Generate filename from URL if not provided
            if filename is None:
                # Get current URL
                current_url = self.page.url
                
                # Parse URL to get domain and path
                parsed_url = urlparse(current_url)
                domain = parsed_url.netloc.replace('www.', '')
                path = parsed_url.path.strip('/')
                
                # Create a clean filename from domain and path
                # Replace non-alphanumeric characters with underscores
                clean_domain = re.sub(r'[^\w\-]', '_', domain)
                clean_path = re.sub(r'[^\w\-]', '_', path) if path else 'home'
                
                # Add timestamp to ensure uniqueness
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Combine into filename
                if clean_path and clean_path != 'home':
                    filename = f"{clean_domain}_{clean_path}_{timestamp}.png"
                else:
                    filename = f"{clean_domain}_{timestamp}.png"
            elif not filename.endswith('.png'):
                filename += '.png'
            
            # Full path to save in screenshots folder
            filepath = os.path.join(screenshots_dir, filename)
            
            # Take screenshot
            self.page.screenshot(path=filepath, full_page=True)
            console.print(f"[green]Screenshot saved:[/green] {filepath}")
            self.log_action("screenshot", filepath, success=True)
            return True
        except Exception as e:
            console.print(f"[red]Screenshot failed:[/red] {e}")
            self.log_action("screenshot", str(e), success=False)
            return False

    def new_tab(self, url: str = None):
        """
        Open a new tab.
        Usage: new_tab [url]
        """
        try:
            # Create new page (tab)
            new_page = self.context.new_page()
            
            # Navigate if URL provided
            if url:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                new_page.goto(url, timeout=self.timeout)
                console.print(f"[green]New tab opened:[/green] {url}")
            else:
                console.print("[green]New blank tab opened[/green]")
            
            # Switch to the new tab
            self.page = new_page
            self.log_action("new_tab", url or "blank", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to open new tab:[/red] {e}")
            self.log_action("new_tab", str(e), success=False)
            return False

    def close_tab(self, index: str = None):
        """
        Close current tab or specified tab by index.
        Usage: close_tab [index]
        """
        try:
            all_pages = self.context.pages
            
            if len(all_pages) <= 1:
                console.print("[yellow]Cannot close last tab[/yellow]")
                return False
            
            # Determine which tab to close
            if index is None:
                # Close current tab
                tab_to_close = self.page
                console.print("[yellow]Closing current tab...[/yellow]")
            else:
                # Close specified tab
                try:
                    idx = int(index)
                    if idx < 1 or idx > len(all_pages):
                        console.print(f"[red]Invalid tab index:[/red] {idx} (valid: 1-{len(all_pages)})")
                        return False
                    tab_to_close = all_pages[idx - 1]
                except ValueError:
                    console.print(f"[red]Invalid index:[/red] {index} (must be a number)")
                    return False
            
            # Close the tab
            tab_to_close.close()
            
            # If we closed the current tab, switch to another one
            if tab_to_close == self.page:
                self.page = self.context.pages[-1]
                self.page.bring_to_front()
            
            console.print(f"[green]Tab closed. Current tab:[/green] {self.page.url}")
            self.log_action("close_tab", index or "current", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to close tab:[/red] {e}")
            self.log_action("close_tab", str(e), success=False)
            return False

    def switch_tab(self, index: str):
        """
        Switch to tab by index.
        Usage: switch_tab <index>
        """
        try:
            idx = int(index)
            all_pages = self.context.pages
            
            if idx < 1 or idx > len(all_pages):
                console.print(f"[red]Invalid tab index:[/red] {idx} (valid: 1-{len(all_pages)})")
                return False
            
            # Switch to tab (convert to 0-indexed)
            self.page = all_pages[idx - 1]
            
            # Explicitly bring tab to front
            self.page.bring_to_front()
            
            console.print(f"[green]Switched to tab {idx}:[/green] {self.page.url}")
            self.log_action("switch_tab", str(idx), success=True)
            return True
            
        except ValueError:
            console.print(f"[red]Invalid index:[/red] {index} (must be a number)")
            return False
        except Exception as e:
            console.print(f"[red]Failed to switch tab:[/red] {e}")
            self.log_action("switch_tab", str(e), success=False)
            return False

    def tabs(self):
        """
        List all open tabs.
        Usage: tabs
        """
        try:
            all_pages = self.context.pages
            
            console.print(f"\n[bold cyan]Open Tabs ({len(all_pages)}):[/bold cyan]")
            
            for idx, page in enumerate(all_pages, start=1):
                is_current = "→" if page == self.page else " "
                title = page.title()[:50] or "Untitled"
                url = page.url[:60]
                console.print(f"{is_current} [{idx}] {title}")
                console.print(f"      [dim]{url}[/dim]")
            
            console.print()
            self.log_action("tabs", f"{len(all_pages)} tabs", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to list tabs:[/red] {e}")
            self.log_action("tabs", str(e), success=False)
            return False

    def clear_cache(self):
        """
        Clear browser cache and cookies.
        Usage: clear_cache
        """
        try:
            console.print("[yellow]Clearing cache and cookies...[/yellow]")
            
            # Store current URL to reload after clearing
            current_url = self.page.url if self.page else None
            
            # Clear cookies
            self.context.clear_cookies()
            
            # Clear storage (localStorage, sessionStorage, etc.)
            if self.page:
                self.page.evaluate("""
                    () => {
                        localStorage.clear();
                        sessionStorage.clear();
                    }
                """)
            
            console.print("[green]Cache and cookies cleared[/green]")
            
            # Reload current page if there was one
            if current_url and current_url != "about:blank":
                console.print(f"[dim]Reloading: {current_url}[/dim]")
                self.page.reload()
            
            self.log_action("clear_cache", "success", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to clear cache:[/red] {e}")
            self.log_action("clear_cache", str(e), success=False)
            return False

    def text_all(self, filename: str = None):
        """
        Extract page content as hierarchically structured Markdown.
        Usage: text_all [filename]
        """
        try:
            import os
            import re
            from datetime import datetime
            
            # Extract structured content with hierarchy
            content_data = self.page.evaluate("""
                () => {
                    const result = {
                        title: document.title || 'Untitled Page',
                        sections: [],
                        footer: ''
                    };
                    
                    // Get main content area
                    const mainArea = document.querySelector('main, article, [role="main"]') || document.body;
                    
                    // Clone to avoid modifying original
                    const clone = mainArea.cloneNode(true);
                    
                    // Remove unwanted elements
                    clone.querySelectorAll('script, style, nav, header, footer, [role="navigation"], .ad, .advertisement').forEach(el => el.remove());
                    
                    // Get all children in order
                    const walker = document.createTreeWalker(
                        clone,
                        NodeFilter.SHOW_ELEMENT,
                        null,
                        false
                    );
                    
                    let currentSection = null;
                    const sections = [];
                    
                    let node;
                    while (node = walker.nextNode()) {
                        const tagName = node.tagName.toLowerCase();
                        
                        // Check if it's a header
                        if (/^h[1-6]$/.test(tagName)) {
                            const level = parseInt(tagName[1]);
                            const text = node.innerText.trim();
                            
                            if (text.length > 0) {
                                currentSection = {
                                    level: level,
                                    title: text,
                                    content: []
                                };
                                sections.push(currentSection);
                            }
                        }
                        // Check if it's content (p, div, ul, ol, etc.)
                        else if (['p', 'div', 'ul', 'ol', 'blockquote', 'pre'].includes(tagName)) {
                            const text = node.innerText.trim();
                            
                            if (text.length >= 10 && currentSection) {
                                // Avoid duplicates (child elements of divs)
                                if (!currentSection.content.includes(text)) {
                                    currentSection.content.push(text);
                                }
                            }
                        }
                    }
                    
                    result.sections = sections;
                    
                    // Extract footer
                    const footer = document.querySelector('footer');
                    if (footer) {
                        result.footer = footer.innerText.trim().replace(/\\s+/g, ' ');
                    }
                    
                    return result;
                }
            """)
            
            if not content_data or len(content_data.get('sections', [])) == 0:
                console.print("[yellow]No structured content found on page[/yellow]")
                return False
            
            # Create text_exports folder
            exports_dir = "text_exports"
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)
            
            # Generate filename from URL if not provided
            if filename is None:
                # Get current URL and sanitize it
                url = self.page.url
                
                # Extract domain and path
                url_clean = re.sub(r'^https?://', '', url)  # Remove protocol
                url_clean = re.sub(r'[^\w\-_.]', '_', url_clean)  # Replace special chars with underscore
                url_clean = re.sub(r'_+', '_', url_clean)  # Collapse multiple underscores
                url_clean = url_clean.strip('_')  # Remove leading/trailing underscores
                
                # Limit length to avoid filesystem issues
                if len(url_clean) > 100:
                    url_clean = url_clean[:100]
                
                filename = f"{url_clean}.md"
            elif not filename.endswith('.md'):
                filename += '.md'
            
            filepath = os.path.join(exports_dir, filename)
            
            # Build Markdown content with hierarchy
            md_lines = []
            
            # Metadata header
            md_lines.append(f"# {content_data['title']}\n\n")
            md_lines.append(f"**Source:** {self.page.url}  \n")
            md_lines.append(f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n")
            md_lines.append("---\n\n")
            
            # Process sections with proper hierarchy
            total_chars = 0
            for section in content_data['sections']:
                level = section['level']
                title = section['title']
                content = section['content']
                
                # Add header with proper markdown level
                md_lines.append(f"{'#' * level} {title}\n\n")
                
                # Add content paragraphs
                for paragraph in content:
                    if paragraph and len(paragraph.strip()) >= 10:
                        # Clean up whitespace
                        clean_para = ' '.join(paragraph.split())
                        md_lines.append(f"{clean_para}\n\n")
                        total_chars += len(clean_para)
            
            # Footer section
            if content_data['footer']:
                md_lines.append("---\n\n")
                md_lines.append("## Footer\n\n")
                md_lines.append(f"{content_data['footer']}\n\n")
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(md_lines)
            
            console.print(f"[green]Markdown saved:[/green] {filepath}")
            console.print(f"[dim]Sections: {len(content_data['sections'])}, Content: {total_chars} chars[/dim]")
            
            # Preview first section
            if content_data['sections']:
                first = content_data['sections'][0]
                preview = f"{first['title']}: {first['content'][0][:200] if first['content'] else 'No content'}"
                console.print(f"\n[dim]Preview:[/dim] {preview}...\n")
            
            self.log_action("text_all", f"{len(content_data['sections'])} sections -> {filepath}", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to extract text:[/red] {e}")
            self.log_action("text_all", str(e), success=False)
            return False
    

def run_experimental_repl(agent: ExperimentalAgent):
    """REPL with experimental commands added."""
    commands = build_command_registry(agent)
    
    # Add experimental commands
    commands['wiki_test'] = agent.wiki_test  # Add this line
    commands['screenshot'] = agent.screenshot
    commands['new_tab'] = agent.new_tab
    commands['close_tab'] = agent.close_tab
    commands['switch_tab'] = agent.switch_tab
    commands['tabs'] = agent.tabs
    commands['clear_cache'] = agent.clear_cache
    commands['text_all'] = agent.text_all
    
    console.print("\n[bold magenta]🧪 Experimental Workspace[/bold magenta]")
    console.print("[yellow]Extra commands: wiki_test, screenshot, new_tab, close_tab, switch_tab, tabs, clear_cache, text_all[/yellow]")
    console.print("[dim]Type 'help' for standard commands, 'exit' to quit[/dim]\n")
    
    while True:
        try:
            command_line = console.input("[bold magenta]exp> [/bold magenta]").strip()
            
            if not command_line:
                continue
            
            parts = agent._parse_command_line(command_line)
            if parts is None:
                continue
            
            if not parts:
                continue
            
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd in ['exit', 'quit', 'q']:
                agent.log_command(cmd, args, success=True)
                console.print("[yellow]Shutting down...[/yellow]")
                break
            
            if cmd in commands:
                try:
                    commands[cmd](*args)
                    agent.log_command(cmd, args, success=True)
                except TypeError as e:
                    console.print(f"[red]Invalid arguments:[/red] {e}")
                    agent.log_command(cmd, args, success=False, error=str(e))
                except Exception as e:
                    console.print(f"[red]Command failed:[/red] {e}")
                    agent.log_command(cmd, args, success=False, error=str(e))
            else:
                console.print(f"[red]Unknown command:[/red] {cmd}")
                console.print("[dim]Type 'help' to see commands[/dim]")
                agent.log_command(cmd, args, success=False, error="Unknown command")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to quit properly[/yellow]")
        except EOFError:
            console.print("\n[yellow]Shutting down...[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            import traceback
            console.print("[dim]" + traceback.format_exc() + "[/dim]")


def main():
    """Entry point."""
    headless = '--headless' in sys.argv
    
    try:
        with ExperimentalAgent(headless=headless) as agent:
            run_experimental_repl(agent)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Fatal error:[/bold red] {e}")
        import traceback
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)


if __name__ == '__main__':
    main()