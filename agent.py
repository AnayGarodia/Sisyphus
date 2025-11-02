#!/usr/bin/env python3
"""
Single-step LLM browser agent with intelligent execution and context awareness.
Executes ONE command at a time with full observability.
OPTIMIZED: Reduced redundant calls, shorter prompts, smarter navigation handling.
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from commands.registry import get_system_prompt_commands

try:
    from groq import Groq
except ImportError:
    raise ImportError("groq package required. Install with: pip install groq")

try:
    from main import BrowserAgent
except ImportError:
    raise ImportError(
        "Cannot import BrowserAgent. To fix circular dependency:\n"
        "1. Move BrowserAgent to browser_agent.py, OR\n"
        "2. Ensure main.py is in sys.path"
    )

try:
    from browser import console
except ImportError:
    class SimpleConsole:
        def print(self, *args, **kwargs):
            print(*args)
        def input(self, prompt=""):
            return input(prompt)
    console = SimpleConsole()

try:
    from commands import build_command_registry
except ImportError:
    raise ImportError("commands module required")


class ErrorType(Enum):
    """Classification of execution errors."""
    VALIDATION = "validation"
    OVERLAY = "overlay"
    TIMEOUT = "timeout"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class ExecutionResult:
    """Result of command execution with full context."""
    success: bool
    output: str
    command: str
    page_changed: bool = False
    error_type: Optional[ErrorType] = None
    page_title: Optional[str] = None
    page_url: Optional[str] = None


class LLMBrowserAgent:
    """
    Intelligent browser agent with single-step execution.
    
    Key features:
    - One command at a time with full observation
    - Automatic task completion detection
    - Rich context awareness
    - Comprehensive error recovery
    """
    
    MAX_CONVERSATION_MESSAGES = 10
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    DEFAULT_MAX_STEPS = 25
    MAX_CONSECUTIVE_FAILURES = 3
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        headless: bool = False,
        model: Optional[str] = None,
        browser_agent: Optional[Any] = None
    ):
        """Initialize LLM Browser Agent with configuration."""
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Groq API key required. Set GROQ_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model or os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self.client = Groq(api_key=self.api_key)
        
        self.browser = browser_agent if browser_agent is not None else BrowserAgent(headless=headless)
        self._owns_browser = browser_agent is None
        
        try:
            self.commands = build_command_registry(self.browser)
        except Exception as e:
            if self._owns_browser:
                self.browser.close()
            raise RuntimeError(f"Failed to build command registry: {e}")
        
        self.conversation_history: List[Dict[str, str]] = []
        self.api_calls_made = 0
        self.consecutive_failures = 0
        self.step_count = 0
        
        self.system_prompt = self._build_system_prompt()
        
    
    def _build_system_prompt(self) -> str:
        """Build concise system prompt for intelligent execution."""
        from commands.registry import get_system_prompt_commands
        commands_section = get_system_prompt_commands()
        
        return f"""You are a browser automation agent. Execute ONE command per response.

    RESPONSE FORMAT (required):
    THINKING: <brief analysis>
    ACTION: <command>

    When task complete:
    THINKING: <brief explanation>
    FINISH: <summary>

    AVAILABLE COMMANDS:

    Navigation:
    - go <url>- Navigate to URL
    - back / forward / refresh  - Browser navigation
    - new_tab <url>- Open new tab
    - switch_tab <N>- Switch to tab N
    - close_tab- Close current tab

    Understanding:
    - read_page [focus] - Extract text (focus=overview/content/forms/navigation/all)
    - scan [type] - Find elements (type=buttons/inputs/links/all)
    - screenshot [name] - Capture screenshot

    Interaction:
    - click <N>  - Click element N
    - type <N> "text" - Type into element N
    - press <key>- Press key (Enter, Tab, Escape, ArrowDown, etc.)
    - hover <N>- Hover over element N
    - check/uncheck <N>- Toggle checkbox N
    - scroll_to <N>- Scroll to element N

    Info:
    - url / title              - Show current page info

    DONT EXECUTE: read_page [focus], scan [type] EXECUTE IN THIS FORMAT: read_page overview or scan buttons etc.

    CORE PRINCIPLES:

    ACT EFFICIENTLY
    - Only use read_page when you need to READ content (articles, results, instructions, unfamiliar pages)
    - Use scan to find buttons/inputs before clicking/typing. 
    - Remember to rescan when the page changes.
    - You need to press Enter after typing anything. Type does NOT auto-submit forms.
    - Use the most direct command to achieve/reach closer to your goal. Do not use unnecessary commands. 
    - Avoid using very specific urls in go. Use common urls (google.com, amazon.com) or given ones.
    - Only FINISH: when full objective accomplished
    - FINISH is not a command! NEVER WRITE Command: FINISH! ALWAYS use FINISH:"""
        
        
    def _get_page_context(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current page title and URL safely."""
        try:
            title = self.browser.page.title() or "No title"
            url = self.browser.page.url
            return title, url
        except Exception:
            return None, None
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured command or done signal."""
        lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
        
        if not lines:
            return {'error': 'Empty response'}
        
        thinking = ''
        action = ''
        finish = ''
        
        for line in lines:
            upper_line = line.upper()
            
            # Check for FINISH
            if upper_line.startswith('FINISH:'):
                finish = line.split(':', 1)[1].strip() if ':' in line else ''
            # Check for ACTION
            elif upper_line.startswith('ACTION:'):
                action = line.split(':', 1)[1].strip() if ':' in line else ''
            # Check for THINKING
            elif upper_line.startswith('THINKING:'):
                thinking = line.split(':', 1)[1].strip() if ':' in line else ''
            # Legacy COMMAND support
            elif upper_line.startswith('COMMAND:'):
                action = line.split(':', 1)[1].strip() if ':' in line else ''
            # Legacy REASONING support
            elif upper_line.startswith('REASONING:'):
                thinking = line.split(':', 1)[1].strip() if ':' in line else ''
        
        # Check if task is finished
        if finish:
            return {
                'done': True,
                'thinking': thinking,
                'finish_message': finish
            }
        
        # Must have an action
        if not action:
            return {'error': 'No ACTION or FINISH found in response'}
        
        # Check for invalid "DONE" as action
        if action.upper() == 'DONE':
            return {
                'error': 'Invalid response: Use "FINISH:" not "ACTION: DONE"'
            }
        
        return {
            'done': False,
            'thinking': thinking,
            'command': action
        }
    
    def _validate_command(self, command_str: str) -> Tuple[bool, str]:
        """Validate command syntax and prerequisites."""
        try:
            parts = self.browser._parse_command_line(command_str)
        except Exception as e:
            return False, f"Failed to parse: {str(e)}"
        
        if not parts:
            return False, "Empty command"
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd not in self.commands:
            available = ', '.join(sorted(self.commands.keys()))
            return False, f"Unknown command '{cmd}'. Available: {available}"
        
        # Validate element-based commands
        element_commands = ['type', 'click', 'hover', 'scroll_to', 'double_click', 
                           'right_click', 'select', 'check', 'uncheck', 'info']
        
        if cmd in element_commands:
            if not args:
                return False, f"'{cmd}' requires element number"
            
            try:
                element_idx = int(args[0])
            except (ValueError, IndexError):
                return False, f"First argument must be element number (integer)"
            
            if element_idx not in self.browser.element_map:
                available = sorted(self.browser.element_map.keys())
                if available:
                    return False, f"Element {element_idx} not found. Available: {available[:15]}"
                else:
                    return False, f"No elements scanned. Use 'scan inputs' or 'scan buttons' first"
            
            # Special validation for type command
            if cmd == 'type':
                elem_meta = self.browser.element_map[element_idx]
                elem_type = elem_meta.get('type', '').lower()
                
                if elem_type not in ['input', 'textarea']:
                    return False, f"Cannot type into {elem_type}. Use 'scan inputs' to find text fields"
                
                if len(args) < 2:
                    return False, f"'type' requires text: type {element_idx} \"your text\""
        
        if cmd == 'go' and not args:
            return False, "'go' requires URL"
        
        return True, ""
    
    def _execute_command(self, command_str: str) -> ExecutionResult:
        """Execute single command with comprehensive result tracking."""
        # Validate first (no context needed for validation)
        is_valid, error_msg = self._validate_command(command_str)
        if not is_valid:
            return ExecutionResult(
                success=False,
                output=error_msg,
                command=command_str,
                page_changed=False,
                error_type=ErrorType.VALIDATION,
                page_title=None,
                page_url=None
            )
        
        try:
            parts = self.browser._parse_command_line(command_str)
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=f"Parse error: {str(e)}",
                command=command_str,
                page_changed=False,
                error_type=ErrorType.VALIDATION,
                page_title=None,
                page_url=None
            )
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # Capture URL before execution (for change detection only)
        try:
            url_before = self.browser.page.url
        except Exception:
            url_before = None
        
        # Execute command
        try:
            # Special handling for scan command
            if cmd == 'scan':
                self.commands[cmd](*args)
                output = self._format_scan_results()
                return ExecutionResult(
                    success=True,
                    output=output,
                    command=command_str,
                    page_changed=False,
                    page_title=None,
                    page_url=None
                )
            
            # Special handling for title command
            elif cmd == 'title':
                title = self.browser.page.title()
                url = self.browser.page.url
                return ExecutionResult(
                    success=True,
                    output=f"Page title: {title}",
                    command=command_str,
                    page_changed=False,
                    page_title=title,
                    page_url=url
                )
            
            # Special handling for url command
            elif cmd == 'url':
                url = self.browser.page.url
                return ExecutionResult(
                    success=True,
                    output=f"Current URL: {url}",
                    command=command_str,
                    page_changed=False,
                    page_title=None,
                    page_url=url
                )
            
            elif cmd == 'read_page':
                focus = args[0] if args else 'overview'
                # Set aggressive limit based on focus type
                if focus == 'overview':
                    max_chars = 800  # Very short for overview
                elif focus in ['forms', 'navigation']:
                    max_chars = 600  # These are typically short
                else:
                    max_chars = 1200  # content/all - slightly more room
                
                extracted_text = self.commands[cmd](focus, save=False, max_chars=max_chars)
                
                # Get context once
                title = self.browser.page.title()
                url = self.browser.page.url
                
                return ExecutionResult(
                    success=True,
                    output=f"Page content extracted ({len(extracted_text)} chars)\n\n{extracted_text}",
                    command=command_str,
                    page_changed=False,
                    page_title=title,
                    page_url=url
                )
            
            # Special handling for screenshot command
            elif cmd == 'screenshot':
                filename = args[0] if args else None
                success = self.commands[cmd](filename)
                
                if success:
                    output = "Screenshot captured successfully"
                    if filename:
                        output += f": {filename}"
                else:
                    output = "Screenshot failed"
                
                return ExecutionResult(
                    success=success,
                    output=output,
                    command=command_str,
                    page_changed=False,
                    page_title=None,
                    page_url=None
                )
            
            # Execute all other commands
            else:
                self.commands[cmd](*args)
                
                # Determine if this is a navigation command
                navigation_commands = ['go', 'back', 'forward']
                is_navigation = cmd in navigation_commands or (
                    cmd == 'press' and args and args[0].lower() == 'enter'
                )
                
                page_changed = False
                
                # Smart wait for navigation commands
                if is_navigation:
                    try:
                        # Wait for navigation to complete
                        self.browser.page.wait_for_load_state('domcontentloaded', timeout=2000)
                    except Exception:
                        # Timeout is OK - page might not navigate
                        pass
                
                # Check if URL actually changed
                try:
                    url_after = self.browser.page.url
                    page_changed = (url_after != url_before)
                except Exception:
                    page_changed = False
                
                # Only get page context if page actually changed
                if page_changed:
                    try:
                        title = self.browser.page.title()
                        url = url_after
                    except Exception:
                        title = "Unknown"
                        url = url_after or "Unknown"
                    
                    # Clear element map on page change
                    if hasattr(self.browser, "element_map"):
                        self.browser.element_map.clear()
                    
                    output = f"Command '{cmd}' executed successfully"
                    output += f"\n\nPAGE CHANGED - Previous element IDs are now invalid"
                    output += f"\nNew page: {title}"
                    output += f"\nURL: {url}"
                else:
                    # Fast path - no context needed
                    title = None
                    url = None
                    output = f"Command '{cmd}' executed successfully"
                
                return ExecutionResult(
                    success=True,
                    output=output,
                    command=command_str,
                    page_changed=page_changed,
                    page_title=title,
                    page_url=url
                )
        
        except Exception as e:
            error_msg = str(e)
            
            # Classify error
            error_type = ErrorType.UNKNOWN
            if "intercept" in error_msg.lower():
                error_type = ErrorType.OVERLAY
            elif "timeout" in error_msg.lower():
                error_type = ErrorType.TIMEOUT
            elif "not attached" in error_msg.lower() or "detached" in error_msg.lower():
                error_type = ErrorType.STALE
            
            # Truncate long errors
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            
            # Get context on error (helpful for debugging)
            try:
                title = self.browser.page.title()
                url = self.browser.page.url
            except:
                title = None
                url = None
            
            return ExecutionResult(
                success=False,
                output=f"Error: {error_msg}",
                command=command_str,
                page_changed=False,
                error_type=error_type,
                page_title=title,
                page_url=url
            )
        
    def _format_scan_results(self) -> str:
        """Format scan results with clear structure."""
        if not self.browser.element_map:
            return "SCAN COMPLETE: No interactive elements found on this page"
        
        by_type: Dict[str, List[Tuple[int, str]]] = {}
        for idx, meta in self.browser.element_map.items():
            elem_type = meta.get('type', 'unknown').lower()
            label = meta.get('label', 'no label')
            label = label[:80].replace('\n', ' ').strip()
            
            if elem_type not in by_type:
                by_type[elem_type] = []
            by_type[elem_type].append((idx, label))
        
        lines = []
        lines.append(f" SCAN COMPLETE - Found {len(self.browser.element_map)} interactive elements")
        
        # Show inputs and textareas first (most commonly needed)
        for elem_type in ['input', 'textarea', 'button', 'link']:
            if elem_type in by_type:
                items = by_type[elem_type]
                lines.append(f"\n {elem_type.upper()}S ({len(items)}):")
                for idx, label in items[:15]:
                    lines.append(f"  [{idx}] {label}")
                if len(items) > 15:
                    lines.append(f"  ... and {len(items)-15} more {elem_type}s")
        
        # Show other element types
        other_types = [t for t in by_type.keys() 
                      if t not in ['input', 'textarea', 'button', 'link']]
        if other_types:
            lines.append(f"\n OTHER ELEMENTS:")
            for t in other_types:
                count = len(by_type[t])
                lines.append(f"{count} {t}(s)")

        lines.append(" Use these element IDs with: click N, type N \"text\", hover N, etc.")
        
        return "\n".join(lines)
    
    def _build_context_summary(self) -> str:
        """Build human-readable context summary."""
        parts = []
        
        title, url = self._get_page_context()
        
        if title and url:
            if len(title) > 70:
                title = title[:70] + "..."
            parts.append(f"Page: {title}")
            parts.append(f"URL: {url}")
        else:
            parts.append("Page context unavailable")
        
        if self.browser.element_map:
            type_counts = {}
            for meta in self.browser.element_map.values():
                elem_type = meta.get('type', 'unknown').lower()
                type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
            
            elem_summary = ', '.join(f"{count} {typ}" for typ, count in sorted(type_counts.items()))
            parts.append(f"Scanned: {elem_summary}")
        else:
            parts.append("No elements scanned yet")
        
        return " | ".join(parts)
    
    def _call_llm(self, user_message: str) -> str:
        """Call LLM with managed conversation history."""
        self.api_calls_made += 1
        
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Truncate old messages AGGRESSIVELY to keep context small
        history = []
        for msg in self.conversation_history[-self.MAX_CONVERSATION_MESSAGES:]:
            content = msg["content"]
            
            # Very aggressive truncation
            if msg["role"] == "assistant":
                # Assistant messages are usually short, keep them at 150
                if len(content) > 150:
                    content = content[:150] + "..."
            else:
                # User messages (feedback) - truncate heavily
                if len(content) > 500:
                    content = content[:500] + "...[msg truncated]"
            
            history.append({
                "role": msg["role"],
                "content": content
            })
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_tokens=150  # Increased from 50 to give room for THINKING + ACTION
            )
            
            assistant_message = response.choices[0].message.content.strip()
            
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
        
        except Exception as e:
            raise RuntimeError(f"LLM API call failed: {str(e)}")
    
    def _build_feedback(self, result: ExecutionResult, task: str) -> str:
        """Build minimal feedback message for LLM."""
        if result.success:
            output = result.output
            
            # Truncate aggressively
            if result.command.startswith('read_page'):
                if len(output) > 500:
                    output = output[:500] + "\n\n...[truncated for token limit]"
            elif len(output) > 350:
                output = output[:350] + "..."
            
            feedback = f"SUCCESS: {output}"
            
            # Detect stuck scan loops
            if result.command.startswith('scan') and "No interactive elements" in output:
                if hasattr(self, 'consecutive_scan_failures'):
                    self.consecutive_scan_failures += 1
                    if self.consecutive_scan_failures >= 2:
                        feedback += "\n\nNo elements found after multiple scans. Try: read_page OR press keys directly"
                else:
                    feedback += "\n\nNo elements found. Try different approach"
            
            if result.page_changed and result.page_title:
                feedback += f"\n\nPage changed: {result.page_title}"
            
            # Hint for type commands
            if result.command.startswith('type ') and not result.page_changed:
                feedback += "\n\nHINT: Text entered. Press Enter to submit"
            
            # CHANGED: Only ask about completion, don't prompt it every time
            feedback += f"\n\nTask objective: {task}"
            feedback += "\nIs task objective fully achieved? If yes, use FINISH:"
            
        else:
            feedback = f"FAILED: {result.output}"
            if self.consecutive_failures >= 2:
                feedback += f"\n\nTry different approach"
        
        return feedback
        
    def execute_task(self, task: str, max_steps: int = None):
        """Execute task with intelligent single-step execution."""
        if max_steps is None:
            max_steps = self.DEFAULT_MAX_STEPS
        
        console.print(f"[bold cyan] TASK: {task}[/bold cyan]")
        console.print(f"[dim]Model: {self.model} | Max steps: {max_steps}[/dim]\n")
        
        self.step_count = 0
        self.original_task = task
        
        # Get initial command
        try:
            initial_prompt = (
                f" TASK: {task}\n\n"
                f"Analyze this task and provide your FIRST action.\n"
                f"Remember to respond with:\n"
                f"THINKING: <your analysis>\n"
                f"ACTION: <single command>"
            )
            llm_response = self._call_llm(initial_prompt)
        except Exception as e:
            console.print(f"[bold red] LLM Error:[/bold red] {e}")
            return
        
        # Main execution loop
        while self.step_count < max_steps:
            self.step_count += 1
            
            # Parse LLM response
            parsed = self._parse_response(llm_response)
            
            # Handle parse errors
            if 'error' in parsed:
                console.print(f"[red]ï¸  Parse Error:[/red] {parsed['error']}")
                console.print(f"[dim]Raw response: {llm_response[:200]}...[/dim]\n")
                
                try:
                    llm_response = self._call_llm(
                        f" Your response format was invalid: {parsed['error']}\n\n"
                        "Please respond using the EXACT format:\n\n"
                        "THINKING: <one sentence>\n"
                        "ACTION: <single command>\n\n"
                        "OR if task is complete:\n\n"
                        "THINKING: <what you accomplished>\n"
                        "FINISH: <summary>\n\n"
                        "DO NOT write 'ACTION: DONE' - use 'FINISH:' instead!"
                    )
                except Exception as e:
                    console.print(f"[red] LLM Error:[/red] {e}")
                    break
                continue
            
            # Check if task is complete
            if parsed.get('done'):
                thinking = parsed.get('thinking', 'No analysis provided')
                finish_msg = parsed.get('finish_message', 'Task completed')
                
                console.print(f"[bold green] TASK COMPLETED[/bold green]")
                
                if thinking:
                    console.print(f"\n[white] Analysis: {thinking}[/white]")
                console.print(f"[white] Result: {finish_msg}[/white]\n")
                
                console.print(f"[bold cyan] Summary:[/bold cyan]")
                console.print(f"Steps taken: {self.step_count}")
                console.print(f"API calls: {self.api_calls_made}")
                
                title, url = self._get_page_context()
                if title and url:
                    console.print(f"Final page: {title}")
                    console.print(f"Final URL: {url}")
                
                console.print()
                return
            
            # Execute command
            command = parsed['command']
            thinking = parsed.get('thinking', 'No analysis provided')
            
            console.print(f"[bold yellow]Step {self.step_count}[/bold yellow]")
            if thinking:
                console.print(f"[dim] {thinking}[/dim]")
            console.print(f"[cyan] ACTION: {command}[/cyan]")
            
            result = self._execute_command(command)
            
            # Display result
            if result.success:
                console.print(f"[green] SUCCESS[/green]")
                self.consecutive_failures = 0
            else:
                console.print(f"[red] FAILED[/red]")
                self.consecutive_failures += 1
            
            # Show output (truncated for display)
            output_lines = result.output.split('\n')
            for line in output_lines[:12]:
                if line.strip():
                    console.print(f"  {line}")
            if len(output_lines) > 12:
                console.print(f"[dim]  ... ({len(output_lines) - 12} more lines)[/dim]")
            
            console.print()
            
            # Build feedback for next iteration
            feedback = self._build_feedback(result, task)
            
            # Get next command
            try:
                llm_response = self._call_llm(feedback)
            except Exception as e:
                console.print(f"[red] LLM Error:[/red] {e}")
                break
        
        # Max steps reached
        if self.step_count >= max_steps:
            console.print(f"[yellow]ï¸  Maximum steps reached ({max_steps})[/yellow]")
            console.print(f"\n[dim] Final state: {self._build_context_summary()}[/dim]")
            console.print(f"[dim] API calls made: {self.api_calls_made}[/dim]\n")
    
    def interactive_mode(self):
        """Interactive mode for continuous task execution."""
        console.print("[bold green]     INTELLIGENT BROWSER AGENT v2.0      [/bold green]")
        console.print(f"[dim]Model: {self.model}[/dim]")
        console.print(f"[dim]Mode: Single-step execution with full observability[/dim]")
        console.print(f"[dim]Commands: 'quit' to exit | 'reset' to restart browser[/dim]\n")
        
        try:
            while True:
                try:
                    task = console.input("[bold blue] Task> [/bold blue]").strip()
                except EOFError:
                    break
                
                if not task:
                    continue
                
                if task.lower() in ['quit', 'exit', 'q']:
                    console.print("[dim] Shutting down...[/dim]")
                    break
                
                if task.lower() == 'reset':
                    console.print("[yellow] Resetting browser...[/yellow]")
                    try:
                        if self._owns_browser:
                            self.browser.close()
                        self.browser = BrowserAgent(headless=False)
                        self.commands = build_command_registry(self.browser)
                        self._owns_browser = True
                        console.print("[green] Browser reset complete[/green]\n")
                    except Exception as e:
                        console.print(f"[red] Reset failed: {e}[/red]\n")
                    continue
                
                # Reset conversation state for new task
                self.conversation_history = []
                self.api_calls_made = 0
                self.consecutive_failures = 0
                
                try:
                    self.execute_task(task)
                except KeyboardInterrupt:
                    console.print("\n[yellow]ï¸  Task interrupted[/yellow]\n")
                except Exception as e:
                    console.print(f"[red] Task execution error: {e}[/red]\n")
                    if os.getenv("DEBUG"):
                        import traceback
                        console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
        
        except KeyboardInterrupt:
            console.print("\n[dim] Interrupted[/dim]")
        
        finally:
            self.close()
    
    def close(self):
        """Clean up resources."""
        if self._owns_browser and hasattr(self, 'browser'):
            try:
                self.browser.close()
            except Exception:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def main():
    """Main entry point with CLI argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Intelligent Single-Step Browser Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --headless                    # Run in headless mode
  %(prog)s --model meta-llama/llama-guard-4-12b  # Use larger model
  %(prog)s --max-steps 50                # Allow more steps
        """
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no GUI)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default=os.getenv('GROQ_MODEL', LLMBrowserAgent.DEFAULT_MODEL),
        help=f'LLM model to use (default: {LLMBrowserAgent.DEFAULT_MODEL})'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='Groq API key (or set GROQ_API_KEY env var)'
    )
    
    parser.add_argument(
        '--max-steps',
        type=int,
        default=25,
        help='Maximum steps per task (default: 25)'
    )
    
    args = parser.parse_args()
    
    try:
        with LLMBrowserAgent(
            api_key=args.api_key,
            headless=args.headless,
            model=args.model
        ) as agent:
            agent.DEFAULT_MAX_STEPS = args.max_steps
            agent.interactive_mode()
    
    except KeyboardInterrupt:
        console.print("\n[dim] Interrupted[/dim]")
        sys.exit(130)
    
    except ValueError as e:
        console.print(f"[bold red] Configuration Error:[/bold red] {e}")
        console.print("[dim]Set GROQ_API_KEY environment variable or use --api-key[/dim]")
        sys.exit(1)
    
    except Exception as e:
        console.print(f"[bold red] Fatal Error:[/bold red] {e}")
        if os.getenv("DEBUG"):
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == '__main__':
    main()