#!/usr/bin/env python3
"""
Professional browser automation agent with text-based control.
Entry point for the integrated agent.
"""

from browser import BaseBrowserAgent, NavigationMixin, InteractionMixin, ScanningMixin, console
from commands import build_command_registry, get_command_help
from datetime import datetime
import sys


class BrowserAgent(BaseBrowserAgent, NavigationMixin, InteractionMixin, ScanningMixin):
    """
    Complete browser agent combining all mixins.
    Inherits from mixins first (left-to-right), then base agent.
    """
    def _get_element(self, selector):
        """
        Resolve element by index, label, or CSS selector.
        
        Args:
            selector: int (element_map index), str (label or CSS)
        
        Returns:
            ElementHandle or None
        """
        # Integer index
        if isinstance(selector, int):
            return self.element_map.get(selector, {}).get("handle")
        
        # String handling
        if isinstance(selector, str):
            selector = selector.strip().strip('"').strip("'")
            
            # Numeric string -> index lookup
            if selector.isdigit():
                idx = int(selector)
                return self.element_map.get(idx, {}).get("handle")
            
            # Label match (case-insensitive)
            for meta in self.element_map.values():
                if meta["label"].lower() == selector.lower():
                    return meta["handle"]
            
            # CSS selector fallback
            try:
                return self.page.query_selector(selector)
            except Exception:
                return None
        
        return None
    
    def help(self, command: str = None):
        """
        Display help information.
        
        Args:
            command: Optional specific command to get help for
        """
        help_text = get_command_help()
        
        if command:
            # Show help for specific command
            matching = [cmd for cmd in help_text if cmd.split()[0] == command.lower()]
            
            if matching:
                console.print(f"\n[bold cyan]{matching[0]}[/bold cyan]")
                console.print(f"  {help_text[matching[0]]}\n")
            else:
                console.print(f"[red]Unknown command:[/red] {command}")
                console.print("[dim]Use 'help' to see all commands[/dim]\n")
        else:
            # Show all commands grouped
            console.print("\n[bold cyan]AVAILABLE COMMANDS[/bold cyan]")
            console.print("=" * 80)
            
            groups = {
                'Navigation': ['go', 'refresh', 'back', 'forward', 'home', 'url', 'title', 'history', 'nav_history', 'wait_load'],
                'Interaction': ['click', 'double_click', 'right_click', 'type', 'press', 'hover', 'select', 'check', 'uncheck', 'scroll_to'],
                'Scanning': ['scan', 'info'],
                'System': ['stats', 'help', 'exit/quit']
            }
            
            for group_name, commands in groups.items():
                console.print(f"\n[bold yellow]{group_name}:[/bold yellow]")
                for cmd in commands:
                    for full_cmd, desc in help_text.items():
                        if full_cmd.split()[0] == cmd:
                            console.print(f"  [cyan]{full_cmd:30}[/cyan] {desc}")
                            break
            
            console.print("\n" + "=" * 80)
            console.print("[bold green]QUICK START:[/bold green]")
            console.print("  1. go <url>         # Navigate to a website")
            console.print("  2. scan             # Find interactive elements")
            console.print("  3. click #N         # Click element number N")
            console.print("  4. type #N 'text'   # Type into element N")
            console.print()
        
        self.log_action("help", command or "overview", success=True)


def run_repl(agent: BrowserAgent):
    """
    Run interactive REPL loop.
    
    Args:
        agent: Initialized BrowserAgent instance
    """
    commands = build_command_registry(agent)
    
    console.print("\n[bold green]Browser Agent Ready[/bold green]")
    console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]\n")
    
    while True:
        try:
            # Get user input
            command_line = console.input("[bold blue]> [/bold blue]").strip()
            
            if not command_line:
                continue
            
            # Parse command
            parts = agent._parse_command_line(command_line)
            if parts is None:
                # Parse error already displayed
                continue
            
            if not parts:
                # Empty input
                continue
            
            cmd = parts[0].lower()
            args = parts[1:]
            
            # Handle exit
            if cmd in ['exit', 'quit', 'q']:
                agent.log_command(cmd, args, success=True)
                console.print("[yellow]Shutting down...[/yellow]")
                break
            
            # Execute command
            if cmd in commands:
                try:
                    commands[cmd](*args)
                    agent.log_command(cmd, args, success=True)
                except TypeError as e:
                    # Wrong number of arguments
                    console.print(f"[red]Invalid arguments:[/red] {e}")
                    console.print(f"[dim]Use 'help {cmd}' for usage[/dim]")
                    agent.log_command(cmd, args, success=False, error=str(e))
                except Exception as e:
                    console.print(f"[red]Command failed:[/red] {e}")
                    agent.log_command(cmd, args, success=False, error=str(e))
            else:
                console.print(f"[red]Unknown command:[/red] {cmd}")
                console.print("[dim]Type 'help' to see available commands[/dim]")
                agent.log_command(cmd, args, success=False, error="Unknown command")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to quit properly[/yellow]")
        
        except EOFError:
            # Ctrl+D pressed
            console.print("\n[yellow]Shutting down...[/yellow]")
            break
        
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            import traceback
            console.print("[dim]" + traceback.format_exc() + "[/dim]")

def main():
    """Main entry point."""
    # Parse command-line arguments
    headless = '--headless' in sys.argv
    
    try:
        # Initialize agent
        with BrowserAgent(headless=headless) as agent:
            # Run REPL
            run_repl(agent)
    
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