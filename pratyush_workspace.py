#!/usr/bin/env python3
"""
Pratyush's experimental workspace.
Add to .gitignore - never commit this file.

Use this to test new navigation features before adding to navigation.py.
"""

from browser import BaseBrowserAgent, NavigationMixin, InteractionMixin, ScanningMixin, console
from commands import build_command_registry


class ExperimentalAgent(NavigationMixin, InteractionMixin, ScanningMixin, BaseBrowserAgent):
    """Agent with experimental features."""
    
    def experimental_navigation(self):
        """Test new navigation features here before moving to mixin."""
        console.print("[yellow]Experimental feature - work in progress[/yellow]")
        pass


if __name__ == '__main__':
    # Quick test environment
    agent = ExperimentalAgent(headless=False)
    
    try:
        # Your test code here
        agent.go_to("google.com")
        
        # Test experimental features
        agent.experimental_navigation()
        
        console.input("\n[dim]Press Enter to close...[/dim]")
    
    finally:
        agent.close()