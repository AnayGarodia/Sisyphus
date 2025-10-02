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


def run_experimental_repl(agent: ExperimentalAgent):
    """REPL with experimental commands added."""
    commands = build_command_registry(agent)
    
    # Add experimental commands
    commands['wiki_test'] = agent.wiki_test  # Add this line
    
    console.print("\n[bold magenta]🧪 Experimental Workspace[/bold magenta]")
    console.print("[yellow]Extra commands: wiki_test[/yellow]")
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