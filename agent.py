#!/usr/bin/env python3
"""
LLM-powered browser agent using Groq.
"""

import os
from groq import Groq
from main import BrowserAgent
from browser import console
from commands import build_command_registry
import sys


class LLMBrowserAgent:
    
    def __init__(self, api_key: str = None, headless: bool = False):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY env var")
        
        self.client = Groq(api_key=self.api_key)
        self.browser = BrowserAgent(headless=headless)
        self.commands = build_command_registry(self.browser)
        self.conversation_history = []
        self.last_commands = []
        self.steps_without_navigation = 0  # Track if stuck on same page
        
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return """You are a browser automation assistant. Execute commands to complete user tasks.

Commands:
- go <url> - Navigate to URL
- scan [filter] - Scan page (filters: inputs, buttons, links)
- click <N> - Click element N
- type <N> "text" - Type into input N
- press <key> - Press key (Enter, Tab, Escape)
- DONE - Task complete

Task Completion Rules:
- "Search X" tasks: Type search term, press Enter, when results appear → DONE
- "Go to X" tasks: Navigate to site → DONE
- "Find X" tasks: Navigate and locate content → DONE
- Don't keep scanning/clicking after finding what was requested

Workflow:
1. Navigate to site
2. scan inputs (if search needed)
3. type into search box
4. press Enter
5. Wait for results
6. DONE

Execute ONE command per turn. Just the command, nothing else.
When you've accomplished the user's goal, say DONE."""
    
    def _detect_stuck(self, command: str) -> bool:
        """Detect if agent is stuck (repeating same command or not making progress)."""
        self.last_commands.append(command.strip().lower())
        
        if len(self.last_commands) > 8:
            self.last_commands.pop(0)
        
        # Same command 3 times in a row
        if len(self.last_commands) >= 3:
            if self.last_commands[-3:] == [self.last_commands[-1]] * 3:
                return True
        
        # Too many scans in short period
        recent_scans = sum(1 for cmd in self.last_commands[-5:] if cmd.startswith('scan'))
        if recent_scans >= 4:
            return True
        
        return False
    
    def _execute_command(self, command_str: str) -> dict:
        parts = self.browser._parse_command_line(command_str)
        if not parts:
            return {"success": False, "output": "Empty command"}
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # Track if we're navigating
        if cmd in ['go', 'click', 'press']:
            self.steps_without_navigation = 0
        else:
            self.steps_without_navigation += 1
        
        if cmd not in self.commands:
            return {"success": False, "output": f"Unknown command: {cmd}"}
        
        try:
            if cmd == 'scan':
                self.commands[cmd](*args)
                output = self._format_scan_results()
                return {"success": True, "output": output}
            elif cmd == 'url':
                result = self.commands[cmd](*args)
                return {"success": True, "output": f"URL: {result}"}
            elif cmd == 'title':
                result = self.commands[cmd](*args)
                return {"success": True, "output": f"Title: {result}"}
            else:
                self.commands[cmd](*args)
                return {"success": True, "output": f"OK: {cmd} completed"}
        
        except Exception as e:
            return {"success": False, "output": f"Error: {str(e)}"}
    
    def _format_scan_results(self) -> str:
        if not self.browser.element_map:
            return "No elements found"
        
        # Show only first 8 elements
        lines = ["Found elements:"]
        for idx, meta in list(self.browser.element_map.items())[:8]:
            lines.append(f"[{idx}] {meta['type']}: {meta['label'][:40]}")
        
        if len(self.browser.element_map) > 8:
            lines.append(f"... +{len(self.browser.element_map) - 8} more")
        
        return "\n".join(lines)
    
    def _call_llm(self, user_message: str, add_hint: str = None) -> str:
        """Call LLM with optional hint if stuck."""
        content = user_message
        if add_hint:
            content = f"{user_message}\n\nHINT: {add_hint}"
        
        self.conversation_history.append({
            "role": "user",
            "content": content
        })
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history
        ]
        
        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.1,
            max_tokens=50
        )
        
        assistant_message = response.choices[0].message.content.strip()
        
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    
    def execute_task(self, task: str, max_steps: int = 15):
        console.print(f"\n[bold cyan]Task:[/bold cyan] {task}\n")
        
        self.last_commands = []
        self.steps_without_navigation = 0
        step = 0
        llm_response = self._call_llm(task)
        
        while step < max_steps:
            step += 1
            
            console.print(f"[yellow]Step {step}:[/yellow] [dim]{llm_response}[/dim]")
            
            # Check if done
            if any(word in llm_response.upper() for word in ["DONE", "COMPLETE", "FINISHED"]):
                console.print("\n[green]✓ Task completed[/green]\n")
                break
            
            # Check if stuck
            if self._detect_stuck(llm_response):
                console.print("\n[yellow]⚠ Agent appears stuck - stopping[/yellow]")
                console.print("[dim]Task may be complete or agent is confused[/dim]\n")
                break
            
            # Execute command
            result = self._execute_command(llm_response)
            
            if result["success"]:
                console.print(f"[green]✓[/green] {result['output']}\n")
                feedback = result["output"]
                
                # Add hint if seems stuck on same page
                hint = None
                if self.steps_without_navigation > 4:
                    hint = "If the task is complete, say DONE"
                
                llm_response = self._call_llm(feedback, add_hint=hint)
            else:
                console.print(f"[red]✗[/red] {result['output']}\n")
                llm_response = self._call_llm(f"Error: {result['output']}")
        
        if step >= max_steps:
            console.print(f"[yellow]Max steps reached ({max_steps})[/yellow]\n")
    
    def interactive_mode(self):
        console.print("\n[bold green]LLM Browser Agent[/bold green]")
        console.print("[dim]Examples: 'Search for X on Google', 'Go to Wikipedia'[/dim]")
        console.print("[dim]Type 'quit' to exit[/dim]\n")
        
        try:
            while True:
                task = console.input("[bold blue]Task> [/bold blue]").strip()
                
                if not task:
                    continue
                
                if task.lower() in ['quit', 'exit', 'q']:
                    break
                
                self.conversation_history = []
                
                try:
                    self.execute_task(task)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Task interrupted[/yellow]\n")
                except Exception as e:
                    console.print(f"[red]Error:[/red] {e}\n")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting[/yellow]")
        
        finally:
            self.close()
    
    def close(self):
        self.browser.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def main():
    headless = '--headless' in sys.argv
    
    try:
        with LLMBrowserAgent(headless=headless) as agent:
            agent.interactive_mode()
    
    except KeyboardInterrupt:
        console.print("\n")
        sys.exit(130)
    
    except Exception as e:
        console.print(f"[bold red]Fatal error:[/bold red] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()