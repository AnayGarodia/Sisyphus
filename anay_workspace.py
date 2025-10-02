#!/usr/bin/env python3
"""
Anay's experimental workspace.
Add to .gitignore - never commit this file.

Use this to test new interaction features before adding to interaction.py.
"""

from browser import BaseBrowserAgent, NavigationMixin, InteractionMixin, ScanningMixin, console
from commands import build_command_registry


class ExperimentalAgent(NavigationMixin, InteractionMixin, ScanningMixin, BaseBrowserAgent):
    """Agent with experimental features."""
    
    def experimental_feature(self):
        """Test new features here before moving to mixin."""
        console.print("[yellow]Experimental feature - work in progress[/yellow]")
        pass


if __name__ == '__main__':
    # Quick test environment
    agent = ExperimentalAgent(headless=False)
    
    try:
        # Your test code here
        agent.go_to("example.com")
        agent.scan()
        
        # Test experimental features
        agent.experimental_feature()
        
        console.input("\n[dim]Press Enter to close...[/dim]")
    
    finally:
        agent.close()