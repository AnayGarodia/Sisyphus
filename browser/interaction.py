"""
Interaction mixin for browser agent.
Handles clicks, typing, and form interactions.
"""

import time
from typing import Optional, Union
from .base_agent import console, action_logger, error_logger


class InteractionMixin:
    """
    Element interaction commands.
    Requires: self.page, self._get_element(), self.log_action(), self.element_map
    """
    
    def click(self, selector: Union[int, str], force: bool = False, timeout: Optional[int] = 10000, retries: int = 2) -> bool:
        """
        Click element by index, label, or CSS selector.

        Args:
            selector: Element index (from scan), label, or CSS selector
            force: Skip visibility checks (for covered elements)
            timeout: Override default timeout (ms)
            retries: Retry attempts on failure (default=2)

        Returns:
            True if click succeeded, False otherwise
        """
        wait_time = timeout or self.timeout
        attempt = 0

        while attempt <= retries:
            try:
                element = self._get_element(selector)
                if not element:
                    console.print(f"[red]Element not found:[/red] {selector}")
                    if str(selector).strip().isdigit():
                        console.print("[dim]Run 'scan' first to see available elements[/dim]")
                    self.log_action("click", f"{selector} - not found", success=False)
                    return False

                # Ensure visible/scrollable
                element.scroll_into_view_if_needed(timeout=wait_time)

                # Click with optional force
                element.click(force=force, timeout=wait_time)

                console.print(f"[green]Clicked:[/green] {selector}")
                self.log_action("click", str(selector), success=True)
                return True

            except Exception as e:
                attempt += 1
                if attempt > retries:
                    console.print(f"[red]Click failed after {retries} retries:[/red] {e}")
                    self.log_action("click", f"{selector} - {e}", success=False)
                    return False
                console.print(f"[yellow]Retrying click ({attempt}/{retries})…[/yellow]")


    def double_click(self, selector: Union[int, str], timeout: Optional[int] = None) -> bool:
        """Double-click element with configurable timeout."""
        try:
            element = self._get_element(selector)
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("double_click", f"{selector} - not found", success=False)
                return False

            wait_time = timeout or self.timeout
            element.scroll_into_view_if_needed(timeout=wait_time)
            element.dblclick(timeout=wait_time)

            console.print(f"[green]Double-clicked:[/green] {selector}")
            self.log_action("double_click", str(selector), success=True)
            return True

        except Exception as e:
            console.print(f"[red]Double-click failed:[/red] {e}")
            self.log_action("double_click", f"{selector} - {e}", success=False)
            return False


    def right_click(self, selector: Union[int, str], timeout: Optional[int] = None) -> bool:
        """Right-click element (context menu)."""
        try:
            element = self._get_element(selector)
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("right_click", f"{selector} - not found", success=False)
                return False

            wait_time = timeout or self.timeout
            element.scroll_into_view_if_needed(timeout=wait_time)
            element.click(button='right', timeout=wait_time)

            console.print(f"[green]Right-clicked:[/green] {selector}")
            self.log_action("right_click", str(selector), success=True)
            return True

        except Exception as e:
            console.print(f"[red]Right-click failed:[/red] {e}")
            self.log_action("right_click", f"{selector} - {e}", success=False)
            return False


    def type(self, selector: Union[int, str], text: str, clear: bool = True, delay: int = 50, timeout: Optional[int] = None) -> bool:
        """
        Type text into input or contentEditable field.

        Args:
            selector: Element index, label, or CSS selector
            text: Text to type
            clear: Clear field before typing
            delay: Milliseconds between keystrokes (human-like typing)
            timeout: Override default timeout (ms)

        Returns:
            True if typing succeeded, False otherwise
        """
        try:
            element = self._get_element(selector)
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("type", f"{selector} - not found", success=False)
                return False

            wait_time = timeout or self.timeout

            # Verify it's an input / editable
            is_input = element.evaluate("""
                el => el.tagName === 'INPUT' || 
                    el.tagName === 'TEXTAREA' ||
                    el.isContentEditable ||
                    el.getAttribute('role') === 'textbox'
            """)
            if not is_input:
                console.print(f"[red]Not an input field:[/red] {selector}")
                self.log_action("type", f"{selector} - not input", success=False)
                return False

            # Focus safely (instead of click, which may fail if covered)
            element.focus()

            # Clear if requested
            if clear:
                element.fill('', timeout=wait_time)

            # Type with delay
            element.type(text, delay=delay, timeout=wait_time)

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
    

    def hover(self, selector: Union[int, str], duration: int = 0, timeout: Optional[int] = None) -> bool:
        """
        Hover over element (triggers hover effects/tooltips).

        Args:
            selector: Element index, label, or CSS selector
            duration: How long to remain hovered (ms)
            timeout: Override default timeout (ms)

        Returns:
            True if hover succeeded
        """
        try:
            element = self._get_element(selector)
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("hover", f"{selector} - not found", success=False)
                return False

            wait_time = timeout or self.timeout
            element.scroll_into_view_if_needed(timeout=wait_time)
            element.hover(timeout=wait_time)

            if duration > 0:
                time.sleep(duration / 1000)

            console.print(f"[green]Hovering:[/green] {selector} (duration={duration}ms)")
            self.log_action("hover", f"{selector} ({duration}ms)", success=True)
            return True

        except Exception as e:
            console.print(f"[red]Hover failed:[/red] {e}")
            self.log_action("hover", f"{selector} - {e}", success=False)
            return False


    def select_option(
        self,
        selector: Union[int, str],
        value: str | None = None,
        label: str | None = None,
        index: int | None = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Select option from <select> dropdown.

        Args:
            selector: Select element identifier
            value: Option value attribute
            label: Option visible text
            index: Option index (0-based)
            timeout: Override default timeout (ms)

        Returns:
            True if selection succeeded
        """
        try:
            element = self._get_element(selector)
            if not element:
                console.print(f"[red]Element not found:[/red] {selector}")
                self.log_action("select_option", f"{selector} - not found", success=False)
                return False

            # Verify <select>
            is_select = element.evaluate("el => el.tagName === 'SELECT'")
            if not is_select:
                console.print(f"[red]Not a select element:[/red] {selector}")
                self.log_action("select_option", f"{selector} - not select", success=False)
                return False

            wait_time = timeout or self.timeout
            args = {}
            if value is not None:
                args["value"] = value
            elif label is not None:
                args["label"] = label
            elif index is not None:
                args["index"] = index
            else:
                raise ValueError("Must specify value, label, or index for selection")

            element.select_option(timeout=wait_time, **args)

            chosen = f"value={value}" if value else f"label={label}" if label else f"index={index}"
            console.print(f"[green]Selected {chosen} in {selector}[/green]")
            self.log_action("select_option", f"{selector} → {chosen}", success=True)
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