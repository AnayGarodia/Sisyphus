#!/usr/bin/env python3
"""
Single-step LLM browser agent with intelligent execution and context awareness.
Executes ONE command at a time with full observability.
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

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
    
    MAX_CONVERSATION_MESSAGES = 14
    DEFAULT_MODEL = "llama-3.1-8b-instant"
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
        """Build comprehensive system prompt for intelligent execution."""
        return """You are an expert browser automation assistant. Execute ONE command at a time, observe results, and make intelligent decisions.

═══════════════════════════════════════════════════════════════
AVAILABLE COMMANDS - YOU HAVE ACCESS TO ALL OF THESE
═══════════════════════════════════════════════════════════════

NAVIGATION:
  go <url>           Navigate to URL (simple, fast)
  refresh            Refresh current page
  back               Go back in browser history
  forward            Go forward in browser history
  home               Go to home page
  url                Get current URL
  title              Get page title
  history            Show navigation history
  nav_history        Detailed navigation history
  wait_load          Wait for page to finish loading

INTERACTION:
  click <N>          Click element N
  double_click <N>   Double-click element N
  right_click <N>    Right-click element N
  type <N> "text"    Type text into element N (must be input/textarea)
  press <key>        Press keyboard key (Enter, Tab, Escape, etc)
  hover <N>          Hover over element N
  select <N> "val"   Select option from dropdown N
  check <N>          Check checkbox N
  uncheck <N>        Uncheck checkbox N
  scroll_to <N>      Scroll element N into view

SCANNING:
  scan <filter>      Scan page for elements
                     Filters: inputs, buttons, links 
  info <N>           Get detailed info about element N

SYSTEM:
  stats              Show browser statistics
  help               Show help message

═══════════════════════════════════════════════════════════════
RESPONSE FORMAT
═══════════════════════════════════════════════════════════════

You MUST respond with EXACTLY ONE of:

Option 1 - Execute a command:
COMMAND: <single command>
REASONING: <why this command>

Option 2 - Task complete:
DONE
REASONING: <what you accomplished>

═══════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════

1. SINGLE-STEP EXECUTION
   • Execute ONE command per response
   • Never plan multiple steps ahead
   • Observe result before deciding next action
   • Trust the feedback you receive

2. CONTEXT AWARENESS
   • You receive CURRENT PAGE TITLE and CURRENT PAGE URL after every command
   • You see FULL TERMINAL OUTPUT from commands
   • Use this information to make decisions
   • Compare current state to task goal

3. ELEMENT MANAGEMENT
   • Element numbers change after EVERY scan
   • 'scan inputs' gives you [1,2,3...] that are ALL inputs
   • 'scan buttons' gives you NEW [1,2,3...] that are ALL buttons
   • Use element numbers from the MOST RECENT scan only
   • After page changes, you MUST scan again

4. TASK COMPLETION - KNOW WHEN TO STOP
   
   Check after EVERY step: Is the task complete?
   
   Navigation tasks → DONE immediately after arriving:
   • "Go to X" → Navigate and DONE
   • "Open X website" → Load page and DONE
   
   Action tasks → DONE after action completes:
   • "Search for X" → Type query + press Enter, then DONE
   • "Click X" → Click successfully, then DONE
   
   Page entry tasks → DONE when on the correct page:
   • "Enter X's page" → Navigate to that page, then DONE
   • "Go to profile of X" → Load their profile, then DONE
   
   IMPORTANT: After pressing Enter on a search, wait to see if page changed.
   If the PAGE TITLE indicates you're on the target page, say DONE.
   Don't keep clicking links if you're already where you need to be.

5. ERROR RECOVERY
   • "Element N not found" → Scan again for fresh numbers
   • "Can't type into X" → Wrong element type, scan inputs
   • "Element stale" → Page changed, scan again
   • "Element intercepted" → Try 'press Escape' first

═══════════════════════════════════════════════════════════════
EXAMPLE EXECUTIONS
═══════════════════════════════════════════════════════════════

Task: "Go to google.com"
Step 1:
  COMMAND: go https://google.com
  REASONING: Navigate to Google
  
  [Result shows: CURRENT PAGE TITLE: Google]
  
Step 2:
  DONE
  REASONING: Task was to go to google.com. We've navigated successfully and are on Google's homepage. Task complete.

---

Task: "Search for Python on Wikipedia"
Step 1:
  COMMAND: go https://wikipedia.org
  REASONING: Navigate to Wikipedia first
  
  [Result shows: CURRENT PAGE TITLE: Wikipedia]
  
Step 2:
  COMMAND: scan inputs
  REASONING: Find the search box
  
  [Result shows: Element [5] "Search Wikipedia"]
  
Step 3:
  COMMAND: type 5 "Python"
  REASONING: Type search query into search box
  
  [Result: Typed successfully]
  
Step 4:
  COMMAND: press Enter
  REASONING: Submit the search
  
  [Result shows: CURRENT PAGE TITLE: Python (programming language) - Wikipedia]
  
Step 5:
  DONE
  REASONING: Task was to search for Python on Wikipedia. The PAGE TITLE shows we're now on the Python Wikipedia page. Search is complete.

---

Task: "Go to wiki and enter Kishore Kumar's page"
Step 1:
  COMMAND: go https://wikipedia.org
  REASONING: Navigate to Wikipedia
  
Step 2:
  COMMAND: scan inputs
  REASONING: Find search box to look up Kishore Kumar
  
Step 3:
  COMMAND: type 5 "Kishore Kumar"
  REASONING: Type name into search box
  
Step 4:
  COMMAND: press Enter
  REASONING: Submit search to find his page
  
  [Result shows: CURRENT PAGE TITLE: Kishore Kumar - Wikipedia]
  
Step 5:
  DONE
  REASONING: Task was to enter Kishore Kumar's page. The CURRENT PAGE TITLE shows "Kishore Kumar - Wikipedia" which means we've successfully entered his page. Task complete.

═══════════════════════════════════════════════════════════════
KEY REMINDERS
═══════════════════════════════════════════════════════════════

• Check CURRENT PAGE TITLE after every command
• If it matches your goal, say DONE immediately
• Don't over-explore after completing the task
• Trust the context information you receive
• One command at a time, always"""
    
    def _get_page_context(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current page title and URL safely."""
        try:
            title = self.browser.page.title or "No title"
            url = self.browser.page.url
            return title, url
        except Exception:
            return None, None
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured command or done signal."""
        lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
        
        if not lines:
            return {'error': 'Empty response'}
        
        # Check for DONE
        if lines[0].upper() == 'DONE':
            reasoning = ''
            for line in lines[1:]:
                if line.upper().startswith('REASONING:'):
                    reasoning = line.split(':', 1)[1].strip()
                    break
            return {'done': True, 'reasoning': reasoning}
        
        # Parse COMMAND
        command = ''
        reasoning = ''
        
        for line in lines:
            if line.upper().startswith('COMMAND:'):
                command = line.split(':', 1)[1].strip()
            elif line.upper().startswith('REASONING:'):
                reasoning = line.split(':', 1)[1].strip()
        
        if not command:
            return {'error': 'No command found in response'}
        
        return {'done': False, 'command': command, 'reasoning': reasoning}
    
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
        # Validate first
        is_valid, error_msg = self._validate_command(command_str)
        if not is_valid:
            title, url = self._get_page_context()
            return ExecutionResult(
                success=False,
                output=error_msg,
                command=command_str,
                page_changed=False,
                error_type=ErrorType.VALIDATION,
                page_title=title,
                page_url=url
            )
        
        try:
            parts = self.browser._parse_command_line(command_str)
        except Exception as e:
            title, url = self._get_page_context()
            return ExecutionResult(
                success=False,
                output=f"Parse error: {str(e)}",
                command=command_str,
                page_changed=False,
                error_type=ErrorType.VALIDATION,
                page_title=title,
                page_url=url
            )
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # Capture state before execution
        try:
            url_before = self.browser.page.url
        except Exception:
            url_before = None
        
        # Execute command
        try:
            if cmd == 'scan':
                self.commands[cmd](*args)
                output = self._format_scan_results()
                title, url = self._get_page_context()
                return ExecutionResult(
                    success=True,
                    output=output,
                    command=command_str,
                    page_changed=False,
                    page_title=title,
                    page_url=url
                )
            
            elif cmd == 'go':
                url_arg = args[0] if args else ''
                self.commands[cmd](*args)
                
                title, url_after = self._get_page_context()
                changed = url_after != url_before if url_before else True
                
                output = f"Successfully navigated to {url_arg}"
                if title:
                    output += f"\nPage loaded: {title}"
                
                return ExecutionResult(
                    success=True,
                    output=output,
                    command=command_str,
                    page_changed=changed,
                    page_title=title,
                    page_url=url_after
                )
            
            elif cmd == 'title':
                title, url = self._get_page_context()
                return ExecutionResult(
                    success=True,
                    output=f"Page title: {title}",
                    command=command_str,
                    page_changed=False,
                    page_title=title,
                    page_url=url
                )
            
            elif cmd == 'url':
                title, url = self._get_page_context()
                return ExecutionResult(
                    success=True,
                    output=f"Current URL: {url}",
                    command=command_str,
                    page_changed=False,
                    page_title=title,
                    page_url=url
                )
            
            else:
                # Execute command
                self.commands[cmd](*args)
                
                # Check for page changes
                page_changed = False
                url_after = url_before
                
                try:
                    url_after = self.browser.page.url
                    page_changed = (url_after != url_before)
                except Exception:
                    page_changed = False
                
                # Special handling for Enter key - give page time to navigate
                if cmd == 'press' and args and args[0].lower() == 'enter': # Allow navigation to complete
                    try:
                        url_after_wait = self.browser.page.url
                        if url_after_wait != url_before:
                            page_changed = True
                            url_after = url_after_wait
                    except Exception:
                        pass
                
                title, url_current = self._get_page_context()
                
                # Build output message
                output = f"Command '{cmd}' completed successfully"
                
                if page_changed:
                    output += f"\n\nPAGE NAVIGATION OCCURRED:"
                    output += f"\n  Previous: {url_before}"
                    output += f"\n  Current: {url_current}"
                    if title:
                        output += f"\n  New page: {title}"
                    output += "\n\nWARNING: All previous element numbers are now INVALID"
                    output += "\n         You MUST run 'scan' again before using click/type"
                
                return ExecutionResult(
                    success=True,
                    output=output,
                    command=command_str,
                    page_changed=page_changed,
                    page_title=title,
                    page_url=url_current
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
            
            title, url = self._get_page_context()
            
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
            return "SCAN COMPLETE: No elements found on page"
        
        by_type: Dict[str, List[Tuple[int, str]]] = {}
        for idx, meta in self.browser.element_map.items():
            elem_type = meta.get('type', 'unknown').lower()
            label = meta.get('label', 'no label')
            label = label[:80].replace('\n', ' ').strip()
            
            if elem_type not in by_type:
                by_type[elem_type] = []
            by_type[elem_type].append((idx, label))
        
        lines = []
        lines.append(f"SCAN COMPLETE - Found {len(self.browser.element_map)} elements")
        lines.append("=" * 70)
        
        # Show inputs and textareas first (most commonly needed)
        for elem_type in ['input', 'textarea', 'button', 'link']:
            if elem_type in by_type:
                items = by_type[elem_type]
                lines.append(f"\n{elem_type.upper()}S ({len(items)}):")
                for idx, label in items[:15]:
                    lines.append(f"  [{idx}] {label}")
                if len(items) > 15:
                    lines.append(f"  ... and {len(items)-15} more {elem_type}s")
        
        # Show other element types
        other_types = [t for t in by_type.keys() 
                      if t not in ['input', 'textarea', 'button', 'link']]
        if other_types:
            lines.append(f"\nOTHER ELEMENTS:")
            for t in other_types:
                count = len(by_type[t])
                lines.append(f"  {count} {t}(s)")
        
        lines.append("\n" + "=" * 70)
        lines.append("Use element numbers above with: click N, type N \"text\", etc.")
        
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
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history[-self.MAX_CONVERSATION_MESSAGES:]
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=250
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
        """Build comprehensive feedback message for LLM."""
        lines = []
        
        # Result section
        lines.append("EXECUTION RESULT")
        lines.append("=" * 70)
        lines.append(f"Command: {result.command}")
        lines.append(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        lines.append("")
        
        if result.success:
            lines.append("Output:")
            lines.append(result.output)
        else:
            lines.append("Error:")
            lines.append(result.output)
            
            # Add recovery suggestions
            if result.error_type == ErrorType.VALIDATION:
                lines.append("\nRecovery: Check your command syntax or scan for elements first")
            elif result.error_type == ErrorType.STALE:
                lines.append("\nRecovery: Page changed - run 'scan' again to get fresh element numbers")
            elif result.error_type == ErrorType.OVERLAY:
                lines.append("\nRecovery: Try 'press Escape' to close any overlays, then retry")
            elif result.error_type == ErrorType.TIMEOUT:
                lines.append("\nRecovery: Page is slow - try again or use a different approach")
        
        lines.append("\n" + "=" * 70)
        
        # Current page state - ALWAYS SHOW THIS
        lines.append("\nCURRENT PAGE STATE")
        lines.append("-" * 70)
        
        if result.page_title and result.page_url:
            lines.append(f"CURRENT PAGE TITLE: {result.page_title}")
            lines.append(f"CURRENT PAGE URL: {result.page_url}")
        else:
            lines.append("CURRENT PAGE: Unable to determine")
        
        lines.append("-" * 70)
        
        # Task completion check
        lines.append(f"\nORIGINAL TASK: {task}")
        lines.append("\nTASK COMPLETION CHECK:")
        lines.append("  1. Look at CURRENT PAGE TITLE and CURRENT PAGE URL above")
        lines.append("  2. Does this match what the task asked for?")
        lines.append("  3. If YES -> Respond with: DONE")
        lines.append("  4. If NO -> Respond with: COMMAND: <next single command>")
        
        # Warning for consecutive failures
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            lines.append(f"\nWARNING: {self.consecutive_failures} consecutive failures")
            lines.append("Consider trying a different approach")
        
        return "\n".join(lines)
    
    def execute_task(self, task: str, max_steps: int = None):
        """Execute task with intelligent single-step execution."""
        if max_steps is None:
            max_steps = self.DEFAULT_MAX_STEPS
        
        console.print(f"\n[bold cyan]════════════════════════════════════════[/bold cyan]")
        console.print(f"[bold cyan]TASK: {task}[/bold cyan]")
        console.print(f"[bold cyan]════════════════════════════════════════[/bold cyan]")
        console.print(f"[dim]Model: {self.model} | Max steps: {max_steps}[/dim]\n")
        
        self.step_count = 0
        self.original_task = task
        
        # Get initial command
        try:
            initial_prompt = (
                f"Task: {task}\n\n"
                f"What is the FIRST single command needed to accomplish this task?\n"
                f"Respond with ONE command only."
            )
            llm_response = self._call_llm(initial_prompt)
        except Exception as e:
            console.print(f"[bold red]LLM Error:[/bold red] {e}")
            return
        
        # Main execution loop
        while self.step_count < max_steps:
            self.step_count += 1
            
            # Parse LLM response
            parsed = self._parse_response(llm_response)
            
            # Handle parse errors
            if 'error' in parsed:
                console.print(f"[red]Parse Error:[/red] {parsed['error']}")
                console.print(f"[dim]Response was: {llm_response[:200]}[/dim]\n")
                
                try:
                    llm_response = self._call_llm(
                        f"Your response was invalid: {parsed['error']}\n\n"
                        "Please respond with either:\n"
                        "  COMMAND: <single command>\n"
                        "  REASONING: <why>\n\n"
                        "OR:\n"
                        "  DONE\n"
                        "  REASONING: <what you accomplished>"
                    )
                except Exception as e:
                    console.print(f"[red]LLM Error:[/red] {e}")
                    break
                continue
            
            # Check if task is complete
            if parsed.get('done'):
                reasoning = parsed.get('reasoning', 'No reasoning provided')
                
                console.print(f"\n[bold green]{'=' * 50}[/bold green]")
                console.print(f"[bold green]TASK COMPLETED[/bold green]")
                console.print(f"[bold green]{'=' * 50}[/bold green]")
                console.print(f"\n[white]{reasoning}[/white]\n")
                
                console.print(f"[bold cyan]Summary:[/bold cyan]")
                console.print(f"  Steps taken: {self.step_count}")
                console.print(f"  API calls: {self.api_calls_made}")
                
                title, url = self._get_page_context()
                if title and url:
                    console.print(f"  Final page: {title}")
                    console.print(f"  Final URL: {url}")
                
                console.print()
                return
            
            # Execute command
            command = parsed['command']
            reasoning = parsed.get('reasoning', 'No reasoning provided')
            
            console.print(f"[bold yellow]Step {self.step_count}[/bold yellow]")
            console.print(f"[dim]Reasoning: {reasoning}[/dim]")
            console.print(f"[cyan]Command: {command}[/cyan]")
            
            result = self._execute_command(command)
            
            # Display result
            if result.success:
                console.print(f"[green]Status: SUCCESS[/green]")
                self.consecutive_failures = 0
            else:
                console.print(f"[red]Status: FAILED[/red]")
                self.consecutive_failures += 1
            
            # Show output (truncated for display)
            output_lines = result.output.split('\n')
            for line in output_lines[:10]:
                if line.strip():
                    console.print(f"  {line}")
            if len(output_lines) > 10:
                console.print(f"  ... ({len(output_lines) - 10} more lines)")
            
            console.print()
            
            # Build feedback for next iteration
            feedback = self._build_feedback(result, task)
            
            # Get next command
            try:
                llm_response = self._call_llm(feedback)
            except Exception as e:
                console.print(f"[red]LLM Error:[/red] {e}")
                break
        
        # Max steps reached
        if self.step_count >= max_steps:
            console.print(f"[yellow]{'=' * 50}[/yellow]")
            console.print(f"[yellow]Maximum steps reached ({max_steps})[/yellow]")
            console.print(f"[yellow]{'=' * 50}[/yellow]")
            console.print(f"\n[dim]Final state: {self._build_context_summary()}[/dim]")
            console.print(f"[dim]API calls made: {self.api_calls_made}[/dim]\n")
    
    def interactive_mode(self):
        """Interactive mode for continuous task execution."""
        console.print("\n[bold green]═══════════════════════════════════════════[/bold green]")
        console.print("[bold green]    INTELLIGENT BROWSER AGENT v2.0      [/bold green]")
        console.print("[bold green]═══════════════════════════════════════════[/bold green]")
        console.print(f"[dim]Model: {self.model}[/dim]")
        console.print(f"[dim]Mode: Single-step execution with full observability[/dim]")
        console.print(f"[dim]Commands: 'quit' to exit | 'reset' to restart browser[/dim]\n")
        
        try:
            while True:
                try:
                    task = console.input("[bold blue]Task> [/bold blue]").strip()
                except EOFError:
                    break
                
                if not task:
                    continue
                
                if task.lower() in ['quit', 'exit', 'q']:
                    console.print("[dim]Shutting down...[/dim]")
                    break
                
                if task.lower() == 'reset':
                    console.print("[yellow]Resetting browser...[/yellow]")
                    try:
                        if self._owns_browser:
                            self.browser.close()
                        self.browser = BrowserAgent(headless=False)
                        self.commands = build_command_registry(self.browser)
                        self._owns_browser = True
                        console.print("[green]✓ Browser reset complete[/green]\n")
                    except Exception as e:
                        console.print(f"[red]Reset failed: {e}[/red]\n")
                    continue
                
                # Reset conversation state for new task
                self.conversation_history = []
                self.api_calls_made = 0
                self.consecutive_failures = 0
                
                try:
                    self.execute_task(task)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Task interrupted[/yellow]\n")
                except Exception as e:
                    console.print(f"[red]Task execution error: {e}[/red]\n")
                    if os.getenv("DEBUG"):
                        import traceback
                        console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
        
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/dim]")
        
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
  %(prog)s --model llama-3.1-70b-versatile  # Use larger model
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
        console.print("\n[dim]Interrupted[/dim]")
        sys.exit(130)
    
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("[dim]Set GROQ_API_KEY environment variable or use --api-key[/dim]")
        sys.exit(1)
    
    except Exception as e:
        console.print(f"[bold red]Fatal Error:[/bold red] {e}")
        if os.getenv("DEBUG"):
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == '__main__':
    main()