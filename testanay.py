from playwright.sync_api import sync_playwright
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
from rich.logging import RichHandler
import logging
from working_commands import BaseBrowserAgent, console, action_logger, error_logger, command_logger, parse_command, Console
import shlex
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

class BrowserAgent(BaseBrowserAgent):
    def scan(self, filter_type: Optional[str] = None, max_elements: int = 25) -> bool:
        """Scan the page for interactive elements and assign identifiers."""
        try:
            selectors = {
                'links': 'a[href]:not([href="#"]):not([href=""])',
                'buttons': 'button, input[type="button"], input[type="submit"], [role="button"]:not(a)',
                'inputs': 'input[type="text"], input[type="email"], input[type="password"], input[type="search"], textarea',
                'selects': 'select, [role="listbox"], [role="combobox"]',
                'checkboxes': 'input[type="checkbox"], input[type="radio"]',
                'other_inputs': 'input[type="file"], input[type="number"], input[type="date"], input[type="tel"]'
            }

            if filter_type and filter_type in selectors:
                selectors = {filter_type: selectors[filter_type]}

            self.element_map = {}
            all_elements = []
            seen = set()  # track handles to prevent duplicates

            for element_type, selector in selectors.items():
                elements = self.page.query_selector_all(selector)

                for element in elements:
                    try:
                        if not element.is_visible():
                            continue

                        # unique handle id to prevent duplicates
                        elem_id = id(element)
                        if elem_id in seen:
                            continue
                        seen.add(elem_id)

                        tag = element.evaluate("el => el.tagName.toLowerCase()")
                        label = self._get_element_label(element, tag, element_type)
                        if not label:
                            continue

                        display_type = self._get_display_type(tag, element, element_type)
                        all_elements.append({
                            'label': label,
                            'type': display_type,
                            'element': element,
                            'tag': tag
                        })

                    except Exception as e:
                        error_logger.debug(f"Skipped element: {str(e)}")
                        continue

            type_priority = {'BUTTON': 1, 'INPUT': 2, 'SELECT': 3, 'LINK': 4, 'CHECKBOX': 5, 'OTHER': 6}
            all_elements.sort(key=lambda x: (type_priority.get(x['type'], 999), x['label']))

            truncated = len(all_elements) > max_elements
            if truncated:
                all_elements = all_elements[:max_elements]

            for i, elem in enumerate(all_elements, start=1):
                self.element_map[i] = {
                    "label": elem['label'],
                    "type": elem['type'],
                    "handle": elem['element']
                }

            self._display_clean_scan_results(all_elements, truncated, len(all_elements), filter_type)
            self.log_action("scan", f"Found {len(all_elements)} interactive elements", success=True)
            return True

        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Scan failed: {str(e)}")
            self.log_action("scan", "Scan failed", success=False)
            return False


    def _get_element_label(self, element, tag, element_type):
        """Create a meaningful label for an element"""
        try:
            label_sources = [
                lambda: element.get_attribute("aria-label"),
                lambda: element.get_attribute("title"),
                lambda: element.get_attribute("alt"),
                lambda: element.get_attribute("placeholder"),
                lambda: element.inner_text().strip(),
                lambda: element.get_attribute("value"),
                lambda: element.get_attribute("name"),
                lambda: element.get_attribute("id"),  # ADD THIS
            ]
            
            label = ""
            for get_label in label_sources:
                try:
                    potential_label = get_label()
                    if potential_label and len(potential_label.strip()) > 0:
                        label = potential_label.strip()
                        break
                except:
                    continue
            
            # Special handling for links
            if element_type == 'links' and tag == 'a':
                href = element.get_attribute("href") or ""
                if not label and href:
                    if href.startswith(('http://', 'https://')):
                        label = href.split('/')[-1] or href.split('/')[2]
                    else:
                        label = href
            
            # Clean up the label
            if label:
                label = ' '.join(label.split())
                MAX_LABEL_LENGTH = 60
                TRUNCATE_SUFFIX = "..."
                if len(label) > MAX_LABEL_LENGTH:
                    label = label[:MAX_LABEL_LENGTH - len(TRUNCATE_SUFFIX)] + TRUNCATE_SUFFIX
            
            # If still no label, add more context
            if not label or label == f"Unnamed {tag}":
                # Try to get context from parent or nearby text
                try:
                    parent_text = element.evaluate("""
                        el => {
                            const parent = el.parentElement;
                            if (parent) {
                                const label = parent.querySelector('label');
                                if (label) return label.innerText;
                                return parent.innerText.slice(0, 50);
                            }
                            return '';
                        }
                    """)
                    if parent_text:
                        label = parent_text.strip()[:30] + "..."
                except:
                    pass
                    
            return label or f"Unnamed {tag}"
            
        except:
            return f"Unnamed {tag}"

    def _get_display_type(self, tag, element, element_type):
        """Determine display type for an element"""
        if tag == "a":
            return "LINK"
        elif tag in ["button"]:
            return "BUTTON"
        elif tag == "input":
            input_type = element.get_attribute("type") or "text"
            if input_type in ["checkbox", "radio"]:
                return "CHECKBOX"
            elif input_type in ["button", "submit"]:
                return "BUTTON"
            else:
                return "INPUT"
        elif tag == "textarea":
            return "INPUT"
        elif tag == "select":
            return "SELECT"
        elif element.get_attribute("role") == "button":
            return "BUTTON"
        else:
            return "OTHER"

    def _display_clean_scan_results(self, elements, truncated, total, filter_type):
        """Display scan results in a clean, organized format"""
        
        filter_text = f" ({filter_type})" if filter_type else ""
        console.print(f"\n[bold blue][SCAN]{filter_text}[/bold blue] Found {total} interactive elements:")
        console.print("=" * 70)
        
        if not elements:
            console.print("[bold yellow][INFO][/bold yellow] No interactive elements found.")
            return
        
        # Group by type for better organization
        grouped = {}
        for i, elem in enumerate(elements, 1):
            elem_type = elem['type']
            if elem_type not in grouped:
                grouped[elem_type] = []
            grouped[elem_type].append((i, elem))
        
        # Display each group
        type_colors = {
            'BUTTON': 'green',
            'LINK': 'blue', 
            'INPUT': 'yellow',
            'SELECT': 'magenta',
            'CHECKBOX': 'cyan',
            'OTHER': 'white'
        }
        
        for elem_type in ['BUTTON', 'INPUT', 'LINK', 'SELECT', 'CHECKBOX', 'OTHER']:
            if elem_type in grouped:
                console.print(f"\n[bold {type_colors.get(elem_type, 'white')}]{elem_type}S:[/bold {type_colors.get(elem_type, 'white')}]")
                
                for idx, elem in grouped[elem_type]:
                    console.print(f"  {idx:>2}. {elem['label']}")
        
        console.print("=" * 70)
        
        if truncated:
            console.print(f"[bold yellow][INFO][/bold yellow] Showing first {len(elements)} elements")
        
        console.print(f"[bold green][TIP][/bold green] Use 'click #' where # is the element number")
        console.print(f"[bold green][TIP][/bold green] Use 'scan buttons' or 'scan links' to filter")

    def display_scan_results(self, elements, total, truncated):
        """Format and display scan results in a nice table"""
        if not elements:
            console.print("[bold yellow][WARN][/bold yellow] No interactive elements found.")
            return

        table = Table(title="[bold blue]Interactive Elements Found[/bold blue]", show_lines=True)
        table.add_column("Index", style="cyan", justify="right")
        table.add_column("Label", style="bold")
        table.add_column("Type", style="magenta")
        table.add_column("Selector (debug)", style="dim")

        for idx, (label, el_type, selector) in enumerate(elements, start=1):
            table.add_row(str(idx), label, el_type, selector)

        console.print(table)

        if truncated:
            console.print(
                f"[bold yellow][INFO][/bold yellow] Showing first {len(elements)} of {total} elements. Refine your scan or increase max_elements."
            )

        console.print(
            "[bold yellow][TIP][/bold yellow] Use 'click <label or index>' or 'fill <label> <text>' to interact."
        )

    
    def click(self, selector: str) -> bool:
        """Click an element by index, label, or CSS selector."""
        try:
            selector_str = str(selector).strip()
            element_handle = None
    
            # Case 1: numeric index
            if isinstance(selector, int):
                idx = selector
                if hasattr(self, "element_map") and idx in self.element_map:
                    element_handle = self.element_map[idx]["handle"]
    
            # Case 2: label match
            elif isinstance(selector, str) and selector.strip().isdigit():
                idx = int(selector.strip())
                for idx, meta in self.element_map.items():
                    if meta["label"].lower() == selector_str.lower():
                        element_handle = meta["handle"]
                        break
    
            # Case 3: fallback â†’ treat as raw CSS
            if not element_handle:
                element_handle = self.page.query_selector(selector_str)
    
            if not element_handle:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                self.log_action("click", f"Selector: {selector} - Not found", success=False)
                return False
    
            # Get element type and attributes
            tag_name = element_handle.evaluate("el => el.tagName.toLowerCase()")
            
            # For links, extract href and navigate directly instead of clicking
            if tag_name == "a":
                href = element_handle.get_attribute("href")
                if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    # Convert relative URLs to absolute
                    if not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                        href = urljoin(self.page.url, href)
                        self.page.goto(href, wait_until="domcontentloaded")
                    
                    # Navigate directly instead of clicking
                    self.page.goto(href, wait_until="domcontentloaded")
                    console.print(f"[bold green][INFO][/bold green] Navigated to: {href}")
                    self.log_action("click", f"Index/Label: {selector} - Direct navigation", success=True)
                    return True
    
            # For buttons and other elements, check for problematic attributes and JavaScript
            onclick = element_handle.get_attribute("onclick")
            if onclick and ("window.open" in onclick or "_blank" in onclick):
                # Extract URL from onclick if it's a simple window.open call
                import re
                url_match = re.search(r'window\.open\([\'"]([^\'"]*)[\'"]', onclick)
                if url_match:
                    url = url_match.group(1)
                    if not url.startswith(("http://", "https://")):
                        from urllib.parse import urljoin
                        url = urljoin(self.page.url, url)
                    
                    self.page.goto(url, wait_until="domcontentloaded")
                    console.print(f"[bold green][INFO][/bold green] Extracted URL and navigated to: {url}")
                    self.log_action("click", f"Index/Label: {selector} - Extracted navigation", success=True)
                    return True

            
    
            # Remove problematic attributes before clicking
            element_handle.evaluate("""
                (element) => {
                    element.removeAttribute('target');
                    // Modify onclick if it contains window.open
                    let onclick = element.getAttribute('onclick');
                    if (onclick && onclick.includes('window.open')) {
                        // Try to extract URL and replace with location.href
                        let urlMatch = onclick.match(/window\.open\(['"]([^'"]*)['"]/);
                        if (urlMatch) {
                            element.setAttribute('onclick', `window.location.href='${urlMatch[1]}'`);
                        }
                    }
                }
            """)
    
            # Now perform the click
            element_handle.click()
    
            console.print(f"[bold green][INFO][/bold green] Clicked: {selector}")
            self.log_action("click", f"Index/Label/CSS: {selector}", success=True)
            return True
    
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Failed to click {selector}: {e}")
            self.log_action("click", f"Selector: {selector}", success=False)
            return False


    def expand_dropdown(self, selector):
        """Expand a dropdown or collapsible element"""
        try:
            element = None
            if hasattr(self, 'element_map') and selector in self.element_map:
                element = self.element_map[selector]
            else:
                element = self.page.query_selector(selector)
            
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                return False
            
            # Check if it's already expanded
            is_expanded = element.get_attribute('aria-expanded')
            if is_expanded == 'true':
                console.print(f"[bold yellow][INFO][/bold yellow] Dropdown {selector} is already expanded")
                return True
            
            # Try to expand the dropdown
            element.click()
            
            # Wait a moment for the dropdown to expand
            self.page.wait_for_timeout(500)
            
            # Verify expansion
            is_expanded_after = element.get_attribute('aria-expanded')
            if is_expanded_after == 'true':
                console.print(f"[bold green][INFO][/bold green] Successfully expanded dropdown {selector}")
                self.log_action("expand_dropdown", f"Selector: {selector}", success=True)
                return True
            else:
                console.print(f"[bold yellow][WARN][/bold yellow] Dropdown {selector} may have been activated, but expansion state unclear")
                self.log_action("expand_dropdown", f"Selector: {selector}", success=True)
                return True
                
        except Exception as e:
            self.log_action("expand_dropdown", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to expand dropdown {selector}: {str(e)}")
            return False

    def collapse_dropdown(self, selector):
        """Collapse an expanded dropdown"""
        try:
            element = None
            if hasattr(self, 'element_map') and selector in self.element_map:
                element = self.element_map[selector]
            else:
                element = self.page.query_selector(selector)
            
            if not element:
                console.print(f"[bold red][ERROR][/bold red] Element not found: {selector}")
                return False
            
            # Check if it's already collapsed
            is_expanded = element.get_attribute('aria-expanded')
            if is_expanded == 'false':
                console.print(f"[bold yellow][INFO][/bold yellow] Dropdown {selector} is already collapsed")
                return True
            
            # Try to collapse by clicking again or pressing Escape
            if is_expanded == 'true':
                element.click()
            else:
                # Try pressing Escape key
                self.page.keyboard.press('Escape')
            
            # Wait a moment
            self.page.wait_for_timeout(500)
            
            console.print(f"[bold green][INFO][/bold green] Attempted to collapse dropdown {selector}")
            self.log_action("collapse_dropdown", f"Selector: {selector}", success=True)
            return True
                
        except Exception as e:
            self.log_action("collapse_dropdown", f"Selector: {selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to collapse dropdown {selector}: {str(e)}")
            return False

    def select_dropdown_option(self, dropdown_selector, option_text):
        """Select an option from a dropdown by text content"""
        try: 
            # First expand the dropdown if needed
            self.expand_dropdown(dropdown_selector)
            
            # Wait for dropdown options to appear
            self.page.wait_for_timeout(500)
            
            # Try multiple strategies to find and click the option
            strategies = [
                # Strategy 1: Direct option selector
                f"{dropdown_selector} option:has-text('{option_text}')",
                # Strategy 2: Look for role=option with text
                f"[role='option']:has-text('{option_text}')",
                # Strategy 3: Look for li elements with text (common in custom dropdowns)
                f"li:has-text('{option_text}')",
                # Strategy 4: Look for divs with role=option
                f"div[role='option']:has-text('{option_text}')",
                # Strategy 5: Any clickable element with the text
                f"*:has-text('{option_text}')"
            ]
            
            option_found = False
            for strategy in strategies:
                try:
                    option_elements = self.page.query_selector_all(strategy)
                    for option in option_elements:
                        if option.is_visible() and option_text.lower() in option.inner_text().lower():
                            option.click()
                            console.print(f"[bold green][INFO][/bold green] Selected '{option_text}' from dropdown {dropdown_selector}")
                            self.log_action("select_dropdown_option", f"Dropdown: {dropdown_selector}, Option: {option_text}", success=True)
                            option_found = True
                            break
                    
                    if option_found:
                        break
                        
                except Exception:
                    continue
            
            if not option_found:
                console.print(f"[bold red][ERROR][/bold red] Could not find option '{option_text}' in dropdown {dropdown_selector}")
                self.log_action("select_dropdown_option", f"Dropdown: {dropdown_selector}, Option: {option_text}", success=False)
                return False
            
            return True
            
        except Exception as e:
            self.log_action("select_dropdown_option", f"Dropdown: {dropdown_selector}, Option: {option_text}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to select dropdown option: {str(e)}")
            return False

    def scan_dropdown_options(self, dropdown_selector):
        """Scan and display options available in a dropdown"""
        try:
            # Expand the dropdown first
            if not self.expand_dropdown(dropdown_selector):
                return
            
            # Wait for options to load
            self.page.wait_for_timeout(500)
            
            # Look for dropdown options
            option_selectors = [
                f"{dropdown_selector} option",
                "[role='option']",
                "li[role='option']",
                "div[role='option']",
                ".dropdown-item",
                ".dropdown-option"
            ]
            
            all_options = []
            for selector in option_selectors:
                try:
                    options = self.page.query_selector_all(selector)
                    for option in options:
                        if option.is_visible():
                            text = option.inner_text().strip()
                            value = option.get_attribute('value') or ''
                            if text and text not in [opt['text'] for opt in all_options]:
                                all_options.append({
                                    'text': text,
                                    'value': value,
                                    'element': option
                                })
                except Exception:
                    continue
            
            if all_options:
                console.print(f"\n[bold blue][DROPDOWN OPTIONS][/bold blue] Available options in {dropdown_selector}:")
                console.print("=" * 60)
                for i, option in enumerate(all_options, 1):
                    value_str = f" (value: {option['value']})" if option['value'] and option['value'] != option['text'] else ""
                    console.print(f"  {i:>2}. {option['text']}{value_str}")
                console.print("=" * 60)
                console.print(f"[bold yellow][TIP][/bold yellow] Use 'select_option {dropdown_selector} <option_text>' to select")
            else:
                console.print(f"[bold yellow][WARN][/bold yellow] No options found in dropdown {dropdown_selector}")
            
            self.log_action("scan_dropdown_options", f"Dropdown: {dropdown_selector}, Found: {len(all_options)} options", success=True)
            
        except Exception as e:
            self.log_action("scan_dropdown_options", f"Dropdown: {dropdown_selector}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to scan dropdown options: {str(e)}")

    def wait_for_dynamic_content(self, timeout=5000):
        """Wait for dynamic content to load on the page"""
        try:
            # Wait for any ongoing network requests to complete
            self.page.wait_for_load_state('networkidle', timeout=timeout)
            
            # Also wait a bit for any JavaScript-generated content
            self.page.wait_for_timeout(1000)
            
            console.print(f"[bold green][INFO][/bold green] Waited for dynamic content to load")
            self.log_action("wait_for_dynamic_content", f"Timeout: {timeout}ms", success=True)
            
        except Exception as e:
            self.log_action("wait_for_dynamic_content", f"Timeout: {timeout}ms", success=False)
            console.print(f"[bold yellow][WARN][/bold yellow] Timeout waiting for dynamic content: {str(e)}")
        
    def help(self, command=None):
        """Display help information for commands"""
        try:
            # Simple command descriptions with usage
            commands = {
                "go <url>": "Navigate to a URL",
                "refresh": "Refresh/reload the current page",
                "back": "Navigate back to previous page in browser history", 
                "forward": "Navigate forward to next page in browser history",
                "stop": "Stop the current page from loading",
                "home": "Navigate to home page (Google)",
                "url": "Display the current page URL",
                "title": "Display the current page title", 
                "history [limit]": "Show recent command history (default 10)",
                "url_history": "Show complete URL navigation history",
                "stats": "Show action statistics and session info",
                "scan [filter]": "Scan page for interactive elements (minimal|smart|full)",
                "click <selector>": "Click an element (#N from scan or CSS selector)",
                "right_click <selector>": "Right-click an element",
                "double_click <selector>": "Double-click an element", 
                "middle_click <selector>": "Middle-click an element",
                "type <selector> '<text>'": "Type text into an input field",
                "expand <selector>": "Expand a dropdown or collapsible element",
                "collapse <selector>": "Collapse an expanded dropdown",
                "select_option <dropdown> '<option>'": "Select option from dropdown by text",
                "scan_dropdown <selector>": "Show all available options in a dropdown",
                "wait [timeout_ms]": "Wait for dynamic content to load (default 5000ms)",
                "help [command]": "Show this help message or help for specific command",
                "quit": "Exit the browser agent",
                "exit": "Exit the browser agent"
            }

            
            if command:
                # Show help for specific command
                matching_commands = [cmd for cmd in commands.keys() if cmd.split()[0].lower() == command.lower()]
                if matching_commands:
                    cmd_usage = matching_commands[0]
                    console.print(f"[bold cyan]{cmd_usage}:[/bold cyan] {commands[cmd_usage]}")
                else:
                    console.print(f"[bold red][ERROR][/bold red] Unknown command: {command}")
                    console.print("[bold yellow][TIP][/bold yellow] Use 'help' to see all available commands")
            else:
                # Show all commands
                console.print("[bold blue][HELP][/bold blue] Available Commands:")
                console.print("=" * 80)
                
                for cmd_usage, description in commands.items():
                    console.print(f"[cyan]{cmd_usage}:[/cyan] {description}")
                
                console.print("=" * 80)
                console.print("[bold green][WORKFLOW TIP][/bold green] Typical workflow:")
                console.print("  1. go <url>        # Navigate to website")
                console.print("  2. scan            # Find interactive elements") 
                console.print("  3. click #N        # Click element N")
                console.print("  4. type #N 'text'  # Fill forms")
                
            self.log_action("help", f"Command: {command or 'overview'}", success=True)
            
        except Exception as e:
            self.log_action("help", f"Command: {command or 'all'}", success=False)
            console.print(f"[bold red][ERROR][/bold red] Failed to show help: {str(e)}")

COMMANDS = {
    # Navigation commands
    "go": BrowserAgent.go_to,
    "refresh": BrowserAgent.refresh,
    "back": BrowserAgent.back,
    "forward": BrowserAgent.forward,
    "stop": BrowserAgent.stop,
    "home": BrowserAgent.home,
    
    # Information commands
    "url": BrowserAgent.url,
    "title": BrowserAgent.title,
    "history": BrowserAgent.get_command_history,
    "url_history": BrowserAgent.history_list,
    "stats": BrowserAgent.get_action_stats,
    
    # Interaction commands
    "scan": BrowserAgent.scan,
    "click": BrowserAgent.click,
    "right_click": BrowserAgent.right_click,
    "double_click": BrowserAgent.double_click,
    "middle_click": BrowserAgent.middle_click,
    "type": BrowserAgent.type,
    
    # Dropdown-specific commands
    "expand": BrowserAgent.expand_dropdown,
    "collapse": BrowserAgent.collapse_dropdown,
    "select_option": BrowserAgent.select_dropdown_option,
    "scan_dropdown": BrowserAgent.scan_dropdown_options,
    
    # Utility commands
    "wait": BrowserAgent.wait_for_dynamic_content,
    "help": BrowserAgent.help,
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