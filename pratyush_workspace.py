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

    def read_page(self, focus: str = "overview", save: bool = True):
        """
        Extract page content with intelligent filtering.
        
        Args:
            focus: What to extract
                - "overview" - Title, headings, first paragraphs (auto-filtered by importance)
                - "forms" - Form fields, labels, inputs, buttons
                - "content" - Main article/text content (full)
                - "navigation" - Menus, links, site structure
                - "all" - Everything (no limit)
            save: Whether to save to file (default True)
        
        Usage:
            read_page               - Overview (smart filtered)
            read_page content       - Full content
            read_page forms         - Just forms
            read_page all           - Everything
        """
        try:
            import os
            import re
            from datetime import datetime
            
            # JavaScript extraction with importance scoring
            content_data = self.page.evaluate(f"""
                (focus) => {{
                    const result = {{
                        title: document.title || 'Untitled',
                        url: window.location.href,
                        focus: focus,
                        sections: []
                    }};
                    
                    // Importance scoring for elements
                    const getImportance = (element) => {{
                        let score = 0;
                        const tag = element.tagName.toLowerCase();
                        
                        // Headers are important
                        if (/^h[1-6]$/.test(tag)) {{
                            score = 10 - parseInt(tag[1]); // h1=9, h2=8, etc.
                        }}
                        
                        // Main content areas
                        if (element.closest('main, article, [role="main"]')) score += 5;
                        
                        // Forms and inputs are important
                        if (tag === 'form' || tag === 'input' || tag === 'textarea') score += 8;
                        if (element.closest('form')) score += 3;
                        
                        // First elements matter more
                        const rect = element.getBoundingClientRect();
                        if (rect.top < 500) score += 2; // Above fold
                        
                        // Text length matters
                        const text = element.innerText?.trim() || '';
                        if (text.length > 100 && text.length < 500) score += 2;
                        if (text.length > 500) score += 1;
                        
                        return score;
                    }};
                    
                    // Get main content area
                    const mainArea = document.querySelector('main, article, [role="main"]') || document.body;
                    
                    // Focus-specific extraction
                    if (focus === 'forms') {{
                        // Extract form fields with context
                        const forms = Array.from(document.querySelectorAll('form, input, textarea, select, button'));
                        const formData = forms.map(el => {{
                            const label = el.labels?.[0]?.innerText || 
                                        el.getAttribute('placeholder') || 
                                        el.getAttribute('aria-label') || 
                                        el.name || 'unlabeled';
                            return {{
                                type: el.tagName.toLowerCase(),
                                label: label.substring(0, 100),
                                importance: 10
                            }};
                        }});
                        
                        result.sections = [{{
                            level: 1,
                            title: 'Form Elements',
                            content: formData.map(f => `[${{f.type}}] ${{f.label}}`),
                            importance: 10
                        }}];
                        
                    }} else if (focus === 'navigation') {{
                        // Extract navigation structure
                        const navs = Array.from(document.querySelectorAll('nav, [role="navigation"], header'));
                        const links = navs.flatMap(nav => 
                            Array.from(nav.querySelectorAll('a')).map(a => a.innerText.trim())
                        ).filter(t => t.length > 0 && t.length < 50);
                        
                        result.sections = [{{
                            level: 1,
                            title: 'Navigation',
                            content: links,
                            importance: 8
                        }}];
                        
                    }} else {{
                        // Extract content without cloning (prevents losing elements)
                        const sections = [];
                        let currentSection = null;
                        
                        // Get all potentially interesting elements
                        const elements = Array.from(mainArea.querySelectorAll('h1, h2, h3, h4, h5, h6, p, div, ul, ol, blockquote, article, section'));
                        
                        // Filter out navigation/noise early
                        const contentElements = elements.filter(el => {{
                            // Skip if inside nav, header, footer, ads
                            if (el.closest('nav, header, footer, .ad, [role="navigation"], aside')) {{
                                return false;
                            }}
                            // Skip if it's just a wrapper with no direct text
                            const directText = Array.from(el.childNodes)
                                .filter(n => n.nodeType === Node.TEXT_NODE)
                                .map(n => n.textContent.trim())
                                .join('');
                            
                            const tag = el.tagName.toLowerCase();
                            
                            // Always include headers
                            if (/^h[1-6]$/.test(tag)) {{
                                return el.innerText.trim().length > 0;
                            }}
                            
                            // For other elements, need meaningful text
                            const text = el.innerText?.trim() || '';
                            return text.length >= 10;
                        }});
                        
                        // Process elements
                        const processedElements = new Set();
                        
                        for (const el of contentElements) {{
                            // Skip if we already processed this as part of a parent
                            if (processedElements.has(el)) continue;
                            
                            const tagName = el.tagName.toLowerCase();
                            const importance = getImportance(el);
                            
                            // Headers create sections
                            if (/^h[1-6]$/.test(tagName)) {{
                                const level = parseInt(tagName[1]);
                                const text = el.innerText.trim();
                                
                                if (text.length > 0) {{
                                    currentSection = {{
                                        level: level,
                                        title: text,
                                        content: [],
                                        importance: importance
                                    }};
                                    sections.push(currentSection);
                                    processedElements.add(el);
                                }}
                            }}
                            // Content elements
                            else {{
                                // Get direct text content (avoid nested duplicates)
                                let text = el.innerText.trim();
                                
                                // Skip if any child was already processed
                                const children = Array.from(el.querySelectorAll('*'));
                                if (children.some(child => processedElements.has(child))) {{
                                    continue;
                                }}
                                
                                if (text.length >= 10) {{
                                    // Create default section if none exists
                                    if (!currentSection) {{
                                        currentSection = {{
                                            level: 1,
                                            title: 'Content',
                                            content: [],
                                            importance: 5
                                        }};
                                        sections.push(currentSection);
                                    }}
                                    
                                    currentSection.content.push({{
                                        text: text,
                                        importance: importance
                                    }});
                                    
                                    processedElements.add(el);
                                    
                                    // Mark children as processed to avoid duplicates
                                    children.forEach(child => processedElements.add(child));
                                }}
                            }}
                        }}
                        
                        // Sort sections by importance if overview
                        if (focus === 'overview') {{
                            sections.sort((a, b) => b.importance - a.importance);
                        }}
                        
                        result.sections = sections;
                    }}
                    
                    return result;
                }}
            """, focus)
            
            if not content_data or len(content_data.get('sections', [])) == 0:
                console.print("[yellow]No content found - page might be empty or JS-heavy[/yellow]")
                console.print(f"[dim]Title: {self.page.title()}, URL: {self.page.url}[/dim]")
                return "No content found on page"
            
            # Build markdown
            lines = []
            lines.append(f"# {content_data['title']}\n\n")
            lines.append(f"**Source:** {content_data['url']}\n")
            lines.append(f"**Focus:** {focus}\n")
            lines.append(f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            lines.append("---\n\n")
            
            total_chars = 0
            sections_included = 0
            
            # Apply filtering based on focus
            for section in content_data['sections']:
                # For overview, only include high-importance sections
                if focus == "overview" and section.get('importance', 0) < 5:
                    continue
                
                level = section['level']
                title = section['title']
                content = section['content']
                
                lines.append(f"{'#' * level} {title}\n\n")
                
                # Handle content (could be strings or dicts with importance)
                for item in content:
                    if isinstance(item, dict):
                        text = item['text']
                        importance = item.get('importance', 0)
                        
                        # Skip low-importance content in overview
                        if focus == "overview" and importance < 3:
                            continue
                    else:
                        text = item
                    
                    if len(text.strip()) >= 10:
                        clean = ' '.join(text.split())
                        lines.append(f"{clean}\n\n")
                        total_chars += len(clean)
                
                sections_included += 1
                
                # Stop at reasonable limit for overview
                if focus == "overview" and total_chars > 2000:
                    lines.append("\n*[Overview truncated - use 'read_page content' for full text]*\n")
                    break
            
            result_text = ''.join(lines)
            
            # Save to file if requested
            if save:
                exports_dir = "text_exports"
                if not os.path.exists(exports_dir):
                    os.makedirs(exports_dir)
                
                # Generate filename
                url_clean = re.sub(r'^https?://', '', content_data['url'])
                url_clean = re.sub(r'[^\w\-_.]', '_', url_clean)
                url_clean = re.sub(r'_+', '_', url_clean).strip('_')[:100]
                
                filename = f"{url_clean}_{focus}.md"
                filepath = os.path.join(exports_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(result_text)
                
                console.print(f"[green]✓ Saved:[/green] {filepath}")
                console.print(f"[dim]Sections: {sections_included}, Chars: {total_chars}[/dim]")
            
            # Return string for LLM
            console.print(f"[green]✓ Extracted {total_chars} chars ({sections_included} sections)[/green]")
            return result_text
            
        except Exception as e:
            console.print(f"[red]Failed to read page:[/red] {e}")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return f"Error reading page: {e}"
        
        

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
    commands['read_page'] = agent.read_page
    
    console.print("\n[bold magenta] Experimental Workspace[/bold magenta]")
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