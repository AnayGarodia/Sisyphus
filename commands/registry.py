"""
Command registry mapping command names to agent methods.
Centralizes all available commands for the REPL.
"""

from typing import Dict, Callable


def build_command_registry(agent) -> Dict[str, Callable]:
    """
    Build command registry from agent instance.
    
    Args:
        agent: BrowserAgent instance with all mixins
    
    Returns:
        Dictionary mapping command names to bound methods
    """
    return {
        # Navigation
        'go': agent.go_to,
        'refresh': agent.refresh,
        'reload': agent.refresh,  # alias
        'back': agent.back,
        'forward': agent.forward,
        'home': agent.home,
        'url': agent.url,
        'title': agent.title,
        'history': agent.get_command_history,
        'nav_history': agent.history_list,
        'wait_load': agent.wait_for_load,
        
        # Interaction
        'click': agent.click,
        'double_click': agent.double_click,
        'dblclick': agent.double_click,  # alias
        'right_click': agent.right_click,
        'type': agent.type,
        'press': agent.press_key,
        'hover': agent.hover,
        'select': agent.select_option,
        'check': agent.check,
        'uncheck': lambda sel: agent.check(sel, checked=False),
        'scroll_to': agent.scroll_to,
        
        # Scanning
        'scan': agent.scan,
        'info': agent.get_element_info,
        
        # System
        'stats': agent.get_action_stats,
        'help': agent.help,
    }


def get_command_help() -> Dict[str, str]:
    """
    Get help text for all commands.
    
    Returns:
        Dictionary mapping command names to descriptions
    """
    return {
        # Navigation
        'go <url>': 'Navigate to URL',
        'refresh': 'Reload current page',
        'back': 'Navigate backward in history',
        'forward': 'Navigate forward in history',
        'home': 'Go to Google homepage',
        'url': 'Display current URL',
        'title': 'Display page title',
        'history [N]': 'Show last N commands (default 10)',
        'nav_history': 'Show navigation history',
        'wait_load [ms]': 'Wait for page to load',
        
        # Interaction
        'click <selector>': 'Click element (#N, label, or CSS)',
        'double_click <selector>': 'Double-click element',
        'right_click <selector>': 'Right-click element',
        'type <selector> "text"': 'Type into input field',
        'press <key>': 'Press keyboard key (Enter, Tab, etc.)',
        'hover <selector>': 'Hover over element',
        'select <selector> "option"': 'Select dropdown option',
        'check <selector>': 'Check checkbox',
        'uncheck <selector>': 'Uncheck checkbox',
        'scroll_to <selector>': 'Scroll element into view',
        
        # Scanning
        'scan [filter]': 'Scan page (filter: buttons, inputs, links, etc.)',
        'info <N>': 'Show details for element #N',
        
        # System
        'stats': 'Show session statistics',
        'help [cmd]': 'Show help',
        'exit/quit': 'Close browser and exit',
    }