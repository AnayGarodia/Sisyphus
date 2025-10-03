#!/usr/bin/env python3
"""
Adaptive LLM browser agent - handles any task through iterative planning.
Key principle: Plan small, execute, observe, replan.
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple
from groq import Groq
from main import BrowserAgent
from browser import console
from commands import build_command_registry


class LLMBrowserAgent:
    """Browser agent with adaptive execution strategy."""
    
    def __init__(self, api_key: Optional[str] = None, headless: bool = False, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY environment variable.")
        
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.client = Groq(api_key=self.api_key)
        self.browser = BrowserAgent(headless=headless)
        self.commands = build_command_registry(self.browser)
        
        self.conversation_history: List[Dict] = []
        self.api_calls_made = 0
        self.consecutive_failures = 0
        
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return """You are a browser automation assistant. You work iteratively: plan a few actions, execute, observe results, then plan next steps.

COMMANDS:
- go <url>         - Navigate
- scan <filter>    - Scan (inputs, buttons, links)
- click <N>        - Click element N
- type <N> "text"  - Type into element N
- press <key>      - Press key (Enter, Tab, Escape)
- wait_load        - Wait for page

RESPONSE FORMAT:

Action Plan:
1. command arg
2. command arg
COMPLEXITY: <1-10>
REASONING: <why these actions>

OR

DONE
REASONING: <why complete>

CRITICAL RULES:

1. PLAN SMALL (2-4 actions max per round)
   - Don't plan beyond what you can currently see
   - After navigation/clicks, page changes - you'll replan
   - Multi-step forms reveal fields progressively
   
2. ELEMENT PERSISTENCE
   - 'scan inputs' → elements [1,2,3...] are inputs
   - 'scan buttons' → elements [1,2,3...] are buttons (previous gone)
   - Use elements immediately after scanning
   - After page changes, previous elements invalid
   
3. OBSERVE & ADAPT
   - After each round, you get feedback about what happened
   - If page changed, rescan to see new elements
   - If action failed, try different approach
   - If stuck 3+ rounds, change strategy
   
4. COMPLETION
   - "Search X" → DONE when on results page
   - "Click X" → DONE after clicking
   - "Go to X" → DONE when page loads
   - "Find X" → DONE when element found
   - "Create account/Fill form" → DONE when submitted OR when asked for info you don't have

COMPLEXITY:
1-3: Clear next steps (navigate, simple interaction)
4-6: Moderate (trying different approach, handling errors)
7-10: Very unclear (stuck, need to explore)

EXAMPLES:

Task: "Create Google account"
Round 1: See signup page with First/Last name fields
1. scan inputs
2. type 1 "TestUser"
3. type 2 "Smith"
COMPLEXITY: 2
REASONING: Fill visible fields, will see what comes next

Round 2: After filling, see "Next" button
1. scan buttons
2. click 1
3. wait_load
COMPLEXITY: 2
REASONING: Submit current step, wait for next page

Round 3: New page appeared, need to see what's there
1. scan inputs
COMPLEXITY: 1
REASONING: Page changed, must scan to see new fields

Task: "Search Python and click first result"
Round 1:
1. go https://google.com
2. wait_load
3. scan inputs
4. type 1 "Python"
COMPLEXITY: 2
REASONING: Navigate and start search

Round 2: After typing
1. press Enter
2. wait_load
COMPLEXITY: 1
REASONING: Execute search

Round 3: On results page
1. scan links
2. click 3
COMPLEXITY: 2
REASONING: Find and click first actual result

Round 4: After clicking, navigated to result page
DONE
REASONING: Clicked result link, task complete

KEY INSIGHT: You don't need to see the whole form/workflow upfront. Just handle what's currently visible, then adapt when page changes."""
    
    def _parse_action_plan(self, response: str) -> Dict:
        """Parse LLM response."""
        lines = [l.strip() for l in response.strip().split('\n') if l.strip()]
        
        if lines and lines[0].upper() == 'DONE':
            reasoning = ''
            for line in lines[1:]:
                if line.startswith('REASONING:'):
                    reasoning = line.split('REASONING:', 1)[1].strip()
                    break
            return {'done': True, 'reasoning': reasoning, 'actions': [], 'complexity': 0}
        
        actions = []
        complexity = 5
        reasoning = ''
        
        for line in lines:
            match = re.match(r'^\d+\.\s+(.+)$', line)
            if match:
                actions.append(match.group(1).strip())
            elif line.startswith('COMPLEXITY:'):
                try:
                    complexity = max(1, min(10, int(re.search(r'\d+', line).group())))
                except:
                    complexity = 5
            elif line.startswith('REASONING:'):
                reasoning = line.split('REASONING:', 1)[1].strip()
        
        # Limit to max 5 actions per round (safety)
        if len(actions) > 5:
            actions = actions[:5]
        
        return {'done': False, 'reasoning': reasoning, 'actions': actions, 'complexity': complexity}
    
    def _validate_action(self, command_str: str) -> Tuple[bool, str]:
        """Validate action before execution."""
        parts = self.browser._parse_command_line(command_str)
        if not parts:
            return False, "Empty command"
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd in ['type', 'click', 'hover', 'scroll_to'] and args:
            try:
                element_idx = int(args[0])
                
                if element_idx not in self.browser.element_map:
                    available = list(self.browser.element_map.keys())
                    return False, f"Element {element_idx} doesn't exist. Available: {available if available else 'none - scan first'}"
                
                if cmd == 'type':
                    elem_type = self.browser.element_map[element_idx]['type'].lower()
                    if elem_type not in ['input', 'textarea']:
                        return False, f"Element {element_idx} is '{elem_type}', can't type into it"
            except (ValueError, IndexError):
                pass
        
        return True, ""
    
    def _execute_command(self, command_str: str) -> Dict:
        """Execute command and return detailed result."""
        is_valid, error_msg = self._validate_action(command_str)
        if not is_valid:
            return {
                "success": False,
                "output": error_msg,
                "command": command_str,
                "error_type": "validation",
                "page_changed": False
            }
        
        parts = self.browser._parse_command_line(command_str)
        if not parts:
            return {"success": False, "output": "Empty command", "command": command_str, "page_changed": False}
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        try:
            url_before = self.browser.driver.current_url
        except:
            url_before = None
        
        if cmd not in self.commands:
            return {"success": False, "output": f"Unknown: {cmd}", "command": command_str, "page_changed": False}
        
        try:
            if cmd == 'scan':
                self.commands[cmd](*args)
                output = self._format_scan_results()
                return {"success": True, "output": output, "command": command_str, "page_changed": False}
            
            elif cmd == 'go':
                self.commands[cmd](*args)
                try:
                    url_after = self.browser.driver.current_url
                    changed = url_after != url_before
                except:
                    changed = True
                return {"success": True, "output": f"Navigated to {args[0] if args else 'page'}", "command": command_str, "page_changed": changed}
            
            else:
                self.commands[cmd](*args)
                
                # Check for page change
                try:
                    url_after = self.browser.driver.current_url
                    page_changed = url_after != url_before
                except:
                    page_changed = False
                
                output = f"{cmd} completed"
                if page_changed:
                    output += f" (page changed to {url_after})"
                
                return {"success": True, "output": output, "command": command_str, "page_changed": page_changed}
        
        except Exception as e:
            error_msg = str(e)
            error_type = "unknown"
            
            if "intercepts pointer" in error_msg or "intercepted" in error_msg:
                error_type = "overlay"
            elif "Timeout" in error_msg or "timeout" in error_msg:
                error_type = "timeout"
            elif "not attached" in error_msg or "detached" in error_msg:
                error_type = "stale"
            
            return {
                "success": False,
                "output": f"Error: {error_msg[:120]}",
                "command": command_str,
                "error_type": error_type,
                "page_changed": False
            }
    
    def _format_scan_results(self) -> str:
        """Format scan results clearly."""
        if not self.browser.element_map:
            return "No elements found on page"
        
        by_type: Dict[str, List[Tuple[int, str]]] = {}
        for idx, meta in self.browser.element_map.items():
            elem_type = meta['type'].lower()
            if elem_type not in by_type:
                by_type[elem_type] = []
            label = meta['label'][:60].replace('\n', ' ')
            by_type[elem_type].append((idx, label))
        
        lines = [f"Found {len(self.browser.element_map)} elements"]
        
        for elem_type in ['input', 'textarea', 'button', 'link']:
            if elem_type in by_type:
                items = by_type[elem_type]
                lines.append(f"\n{elem_type.upper()}S:")
                for idx, label in items[:8]:
                    lines.append(f"  [{idx}] {label}")
                if len(items) > 8:
                    lines.append(f"  ...+{len(items)-8} more")
        
        return "\n".join(lines)
    
    def _build_context(self) -> str:
        """Build context summary."""
        parts = []
        
        try:
            url = self.browser.driver.current_url
            title = self.browser.driver.title
            parts.append(f"Current: {title}")
            parts.append(f"URL: {url}")
        except:
            parts.append("Page info unavailable")
        
        if self.browser.element_map:
            types = {}
            for meta in self.browser.element_map.values():
                t = meta['type'].lower()
                types[t] = types.get(t, 0) + 1
            parts.append(f"Elements in map: {', '.join(f'{c} {t}' for t,c in types.items())}")
        else:
            parts.append("No elements currently mapped")
        
        return " | ".join(parts)
    
    def _call_llm(self, user_message: str) -> str:
        """Call LLM with context management."""
        self.api_calls_made += 1
        
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Keep last 5 exchanges (10 messages)
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history[-10:]
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=250
        )
        
        assistant_message = response.choices[0].message.content.strip()
        self.conversation_history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
    
    def execute_task(self, task: str, max_rounds: int = 12):
        """Execute task with adaptive planning."""
        console.print(f"\n[bold cyan]Task:[/bold cyan] {task}")
        console.print(f"[dim]Model: {self.model}[/dim]\n")
        
        round_num = 0
        llm_response = self._call_llm(f"Task: {task}\n\nPlan your first 2-4 actions based on what you need to do first.")
        
        while round_num < max_rounds:
            round_num += 1
            
            plan = self._parse_action_plan(llm_response)
            
            if plan['done']:
                console.print(f"\n[bold green]Task Complete[/bold green]")
                if plan['reasoning']:
                    console.print(f"[dim]{plan['reasoning']}[/dim]")
                console.print(f"[dim]Rounds: {round_num}, API calls: {self.api_calls_made}[/dim]\n")
                break
            
            complexity_color = "green" if plan['complexity'] <= 3 else "yellow" if plan['complexity'] <= 6 else "red"
            console.print(f"[bold yellow]Round {round_num}[/bold yellow] [{complexity_color}]Complexity {plan['complexity']}[/{complexity_color}]")
            if plan['reasoning']:
                console.print(f"[dim]{plan['reasoning']}[/dim]")
            
            if not plan['actions']:
                console.print("[yellow]No actions provided[/yellow]")
                context = self._build_context()
                llm_response = self._call_llm(f"You provided no actions.\n\n{context}\n\nEither provide 2-4 actions or respond DONE.")
                continue
            
            # Execute actions
            results = []
            page_changed = False
            
            for i, action in enumerate(plan['actions'], 1):
                console.print(f"  [{i}] {action}")
                
                result = self._execute_command(action)
                results.append(result)
                
                if result['success']:
                    console.print(f"      [green]✓[/green] {result['output']}")
                    if result.get('page_changed'):
                        page_changed = True
                    self.consecutive_failures = 0
                else:
                    console.print(f"      [red]✗[/red] {result['output']}")
                    self.consecutive_failures += 1
                    break  # Stop on error
            
            console.print()
            
            # Build feedback
            feedback = []
            
            all_succeeded = all(r['success'] for r in results)
            
            if all_succeeded:
                feedback.append(f"All {len(results)} actions completed successfully")
                if page_changed:
                    feedback.append("Page changed - previous elements are now invalid")
            else:
                failed = results[-1]
                feedback.append(f"Failed at: {failed['command']}")
                feedback.append(f"Error: {failed['output']}")
                
                error_type = failed.get('error_type')
                if error_type == 'validation':
                    feedback.append("Fix: Element doesn't exist in current scan. Scan again to refresh elements.")
                elif error_type == 'stale':
                    feedback.append("Fix: Page changed, elements stale. Scan again to get current elements.")
                elif error_type == 'overlay':
                    feedback.append("Fix: Something blocking click. Try 'press Escape' then retry.")
            
            # Add scan results if any
            for r in results:
                if 'Found' in r['output'] and 'elements' in r['output']:
                    feedback.append(f"\nScan results:\n{r['output']}")
                    break
            
            # Add current state
            feedback.append(f"\nCurrent state:\n{self._build_context()}")
            
            # Warn if stuck
            if self.consecutive_failures >= 3:
                feedback.append(f"\n⚠ {self.consecutive_failures} consecutive failures - try completely different approach")
            
            feedback_text = "\n".join(feedback)
            
            # Get next plan
            if all_succeeded and page_changed:
                llm_response = self._call_llm(f"{feedback_text}\n\nPage changed. Scan to see new elements, then plan next 2-4 actions.")
            else:
                llm_response = self._call_llm(f"{feedback_text}\n\nPlan next 2-4 actions or respond DONE.")
        
        if round_num >= max_rounds:
            console.print(f"[yellow]Reached max rounds ({max_rounds})[/yellow]")
            console.print(f"[dim]State: {self._build_context()}[/dim]")
            console.print(f"[dim]API calls: {self.api_calls_made}[/dim]\n")
    
    def interactive_mode(self):
        """Interactive task execution."""
        console.print("\n[bold green]Adaptive Browser Agent[/bold green]")
        console.print(f"[dim]Model: {self.model}[/dim]")
        console.print("[dim]Type 'quit' to exit, 'reset' to restart browser[/dim]\n")
        
        try:
            while True:
                task = console.input("[bold blue]Task> [/bold blue]").strip()
                
                if not task:
                    continue
                
                if task.lower() in ['quit', 'exit', 'q']:
                    break
                
                if task.lower() == 'reset':
                    self.browser.close()
                    self.browser = BrowserAgent(headless=False)
                    self.commands = build_command_registry(self.browser)
                    console.print("[green]Browser reset[/green]\n")
                    continue
                
                # Reset state
                self.conversation_history = []
                self.api_calls_made = 0
                self.consecutive_failures = 0
                
                try:
                    self.execute_task(task)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted[/yellow]\n")
                except Exception as e:
                    console.print(f"[red]Error:[/red] {e}\n")
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
        
        except KeyboardInterrupt:
            console.print("\n")
        
        finally:
            self.close()
    
    def close(self):
        """Cleanup."""
        self.browser.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Adaptive Browser Agent')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--model', type=str, default=os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant'))
    
    args = parser.parse_args()
    
    try:
        with LLMBrowserAgent(headless=args.headless, model=args.model) as agent:
            agent.interactive_mode()
    except KeyboardInterrupt:
        console.print("\n")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Fatal:[/bold red] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()