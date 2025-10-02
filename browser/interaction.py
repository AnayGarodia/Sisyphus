"""
Interaction mixin for browser agent.
Handles clicks, typing, and form interactions.
"""

from typing import Optional, Union
from .base_agent import console, action_logger, error_logger


class InteractionMixin:
    """
    Element interaction commands.
    Requires: self.page, self._get_element(), self.log_action(), self.element_map
    """
    
    def click(self, selector: Union[int, str], force: bool = False) -> bool:
        """
        Click element by index, label, or CSS selector.
        
        Args:
            selector: Element index (from scan), label, or CSS selector
            force: Skip visibility checks (for covered elements)
        
        Returns:
            True if click succeeded
        """
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                if str(selector).strip().isdigit():
                    console.print("[dim]Run 'scan' first to see available elements[/dim]")
                self.log_action("click", f"{selector} - not found", success=False)
                return False
            
            # Click with optional force
            element.click(force=force, timeout=5000)
            
            console.print(f"[green]Clicked:[/green] {selector}")
            self.log_action("click", str(selector), success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Click failed:[/red] {e}")
            self.log_action("click", f"{selector} - {e}", success=False)
            return False
    
    def double_click(self, selector: Union[int, str]) -> bool:
        """Double-click element."""
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("double_click", f"{selector} - not found", success=False)
                return False
            
            element.dblclick(timeout=5000)
            
            console.print(f"[green]Double-clicked:[/green] {selector}")
            self.log_action("double_click", str(selector), success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Double-click failed:[/red] {e}")
            self.log_action("double_click", f"{selector} - {e}", success=False)
            return False
    
    def right_click(self, selector: Union[int, str]) -> bool:
        """Right-click element (context menu)."""
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("right_click", f"{selector} - not found", success=False)
                return False
            
            element.click(button='right', timeout=5000)
            
            console.print(f"[green]Right-clicked:[/green] {selector}")
            self.log_action("right_click", str(selector), success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Right-click failed:[/red] {e}")
            self.log_action("right_click", f"{selector} - {e}", success=False)
            return False
    
    def type(self, selector: Union[int, str], text: str, clear: bool = True, delay: int = 50) -> bool:
        """
        Type text into input field.
        
        Args:
            selector: Element index, label, or CSS selector
            text: Text to type
            clear: Clear field before typing
            delay: Milliseconds between keystrokes (human-like typing)
        
        Returns:
            True if typing succeeded
        """
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("type", f"{selector} - not found", success=False)
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
                console.print(f"[red]Not an input field:[/red] {selector}")
                self.log_action("type", f"{selector} - not input", success=False)
                return False
            
            # Focus element
            element.click()
            
            # Clear if requested
            if clear:
                element.fill('')
            
            # Type with delay
            element.type(text, delay=delay)
            
            # Truncate long text in log
            display_text = text if len(text) <= 50 else text[:47] + "..."
            console.print(f"[green]Typed into {selector}:[/green] {display_text}")
            self.log_action("type", f"{selector} ({len(text)} chars)", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Type failed:[/red] {e}")
            self.log_action("type", f"{selector} - {e}", success=False)
            return False
    
    def press_key(self, key: str) -> bool:
        """
        Press keyboard key (e.g., 'Enter', 'Escape', 'Tab').
        
        Args:
            key: Key name (Playwright format)
        
        Returns:
            True if key press succeeded
        """
        try:
            self.page.keyboard.press(key)
            
            console.print(f"[green]Pressed:[/green] {key}")
            self.log_action("press_key", key, success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Key press failed:[/red] {e}")
            self.log_action("press_key", f"{key} - {e}", success=False)
            return False
    
    def hover(self, selector: Union[int, str]) -> bool:
        """
        Hover over element (triggers hover effects/tooltips).
        
        Args:
            selector: Element index, label, or CSS selector
        
        Returns:
            True if hover succeeded
        """
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("hover", f"{selector} - not found", success=False)
                return False
            
            element.hover(timeout=5000)
            
            console.print(f"[green]Hovering:[/green] {selector}")
            self.log_action("hover", str(selector), success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Hover failed:[/red] {e}")
            self.log_action("hover", f"{selector} - {e}", success=False)
            return False
    
    def select_option(self, selector: Union[int, str], value: str) -> bool:
        """
        Select option from <select> dropdown by visible text.
        
        Args:
            selector: Select element identifier
            value: Option text to select
        
        Returns:
            True if selection succeeded
        """
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("select_option", f"{selector} - not found", success=False)
                return False
            
            # Verify it's a select
            is_select = element.evaluate("el => el.tagName === 'SELECT'")
            
            if not is_select:
                console.print(f"[red]Not a select element:[/red] {selector}")
                self.log_action("select_option", f"{selector} - not select", success=False)
                return False
            
            # Select by label text
            element.select_option(label=value, timeout=5000)
            
            console.print(f"[green]Selected '{value}' in {selector}[/green]")
            self.log_action("select_option", f"{selector} → {value}", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Selection failed:[/red] {e}")
            self.log_action("select_option", f"{selector} - {e}", success=False)
            return False
    
    def check(self, selector: Union[int, str], checked: bool = True) -> bool:
        """
        Check or uncheck checkbox/radio button.
        
        Args:
            selector: Element identifier
            checked: True to check, False to uncheck
        
        Returns:
            True if action succeeded
        """
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("check", f"{selector} - not found", success=False)
                return False
            
            if checked:
                element.check(timeout=5000)
                action = "Checked"
            else:
                element.uncheck(timeout=5000)
                action = "Unchecked"
            
            console.print(f"[green]{action}:[/green] {selector}")
            self.log_action("check", f"{selector} → {checked}", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Check/uncheck failed:[/red] {e}")
            self.log_action("check", f"{selector} - {e}", success=False)
            return False
    
    def scroll_to(self, selector: Union[int, str]) -> bool:
        """
        Scroll element into view.
        
        Args:
            selector: Element identifier
        
        Returns:
            True if scroll succeeded
        """
        try:
            element = self._get_element(selector)
            
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("scroll_to", f"{selector} - not found", success=False)
                return False
            
            element.scroll_into_view_if_needed(timeout=5000)
            
            console.print(f"[green]Scrolled to:[/green] {selector}")
            self.log_action("scroll_to", str(selector), success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Scroll failed:[/red] {e}")
            self.log_action("scroll_to", f"{selector} - {e}", success=False)
            return False