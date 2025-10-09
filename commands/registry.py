"""
Command registry mapping command names to agent methods.
Centralizes all available commands for the REPL.
"""

from typing import Dict, Callable, List, Tuple
from dataclasses import dataclass


@dataclass
class CommandSpec:
    """Specification for a single command."""
    name: str
    method_name: str  # Method name on agent instance
    syntax: str  # How to use the command
    description: str
    category: str
    aliases: List[str] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


# ============================================================================
# COMMAND SPECIFICATIONS - Single source of truth
# ============================================================================

COMMAND_SPECS = [
    # Navigation
    CommandSpec(
        name='go',
        method_name='go_to',
        syntax='go <url>',
        description='Navigate to URL',
        category='Navigation'
    ),
    CommandSpec(
        name='refresh',
        method_name='refresh',
        syntax='refresh',
        description='Reload current page',
        category='Navigation',
        aliases=['reload']
    ),
    CommandSpec(
        name='back',
        method_name='back',
        syntax='back',
        description='Navigate backward in history',
        category='Navigation'
    ),
    CommandSpec(
        name='forward',
        method_name='forward',
        syntax='forward',
        description='Navigate forward in history',
        category='Navigation'
    ),
    CommandSpec(
        name='home',
        method_name='home',
        syntax='home',
        description='Go to Google homepage',
        category='Navigation'
    ),
    CommandSpec(
        name='url',
        method_name='url',
        syntax='url',
        description='Display current URL',
        category='Navigation'
    ),
    CommandSpec(
        name='title',
        method_name='title',
        syntax='title',
        description='Display page title',
        category='Navigation'
    ),
    CommandSpec(
        name='history',
        method_name='get_command_history',
        syntax='history [N]',
        description='Show last N commands (default 10)',
        category='Navigation'
    ),
    CommandSpec(
        name='nav_history',
        method_name='history_list',
        syntax='nav_history',
        description='Show navigation history',
        category='Navigation'
    ),
    CommandSpec(
        name='wait_load',
        method_name='wait_for_load',
        syntax='wait_load [ms]',
        description='Wait for page to load',
        category='Navigation'
    ),
    
    # Interaction
    CommandSpec(
        name='click',
        method_name='click',
        syntax='click <selector>',
        description='Click element (#N, label, or CSS)',
        category='Interaction'
    ),
    CommandSpec(
        name='double_click',
        method_name='double_click',
        syntax='double_click <selector>',
        description='Double-click element',
        category='Interaction',
        aliases=['dblclick']
    ),
    CommandSpec(
        name='right_click',
        method_name='right_click',
        syntax='right_click <selector>',
        description='Right-click element',
        category='Interaction'
    ),
    CommandSpec(
        name='type',
        method_name='type',
        syntax='type <selector> "text"',
        description='Type into input field',
        category='Interaction'
    ),
    CommandSpec(
        name='press',
        method_name='press_key',
        syntax='press <key>',
        description='Press keyboard key (Enter, Tab, etc.)',
        category='Interaction'
    ),
    CommandSpec(
        name='hover',
        method_name='hover',
        syntax='hover <selector>',
        description='Hover over element',
        category='Interaction'
    ),
    CommandSpec(
        name='select',
        method_name='select_option',
        syntax='select <selector> "option"',
        description='Select dropdown option',
        category='Interaction'
    ),
    CommandSpec(
        name='check',
        method_name='check',
        syntax='check <selector>',
        description='Check checkbox',
        category='Interaction'
    ),
    CommandSpec(
        name='uncheck',
        method_name='check',  # Uses same method with checked=False
        syntax='uncheck <selector>',
        description='Uncheck checkbox',
        category='Interaction'
    ),
    CommandSpec(
        name='scroll_to',
        method_name='scroll_to',
        syntax='scroll_to <selector>',
        description='Scroll element into view',
        category='Interaction'
    ),
    
    # Scanning
    CommandSpec(
        name='scan',
        method_name='scan',
        syntax='scan [filter]',
        description='Scan page (filter: buttons, inputs, links, etc.)',
        category='Scanning'
    ),
    CommandSpec(
        name='info',
        method_name='get_element_info',
        syntax='info <N>',
        description='Show details for element #N',
        category='Scanning'
    ),
    
    # System
    CommandSpec(
        name='stats',
        method_name='get_action_stats',
        syntax='stats',
        description='Show session statistics',
        category='System'
    ),
    CommandSpec(
        name='help',
        method_name='help',
        syntax='help [cmd]',
        description='Show help',
        category='System'
    ),
    CommandSpec(
        name='new_tab',
        method_name='new_tab',  
        syntax='new_tab [url]',
        description='Open a new tab at (optional) URL',
        category='Navigation'
    ),
    CommandSpec(
        name='close_tab',
        method_name='close_tab',  
        syntax='close_tab [index]',
        description='Close current tab or specified tab by index.',
        category='Navigation'
    ),
    CommandSpec(
        name='switch_tab',
        method_name='switch_tab',  
        syntax='switch_tab <index>',
        description='Switch to tab by index.',
        category='Navigation'
    ),
    CommandSpec(
        name='tabs',
        method_name='tabs',  
        syntax='tabs',
        description='List all open tabs.',
        category='Navigation'
    ),

]


# ============================================================================
# REGISTRY BUILDERS
# ============================================================================

def build_command_registry(agent) -> Dict[str, Callable]:
    """
    Build command registry from agent instance.
    
    Args:
        agent: BrowserAgent instance with all mixins
    
    Returns:
        Dictionary mapping command names to bound methods
    """
    registry = {}
    
    for spec in COMMAND_SPECS:
        # Get the method from agent
        method = getattr(agent, spec.method_name)
        
        # Handle special cases (like uncheck)
        if spec.name == 'uncheck':
            registry[spec.name] = lambda sel, m=method: m(sel, checked=False)
        else:
            registry[spec.name] = method
        
        # Add aliases
        for alias in spec.aliases:
            registry[alias] = registry[spec.name]
    
    return registry


def get_command_help() -> Dict[str, str]:
    """
    Get help text for all commands.
    
    Returns:
        Dictionary mapping command syntax to descriptions
    """
    help_dict = {}
    
    for spec in COMMAND_SPECS:
        help_dict[spec.syntax] = spec.description
    
    return help_dict


def get_commands_by_category() -> Dict[str, List[str]]:
    """
    Get commands grouped by category.
    
    Returns:
        Dictionary mapping category names to lists of command names
    """
    categories = {}
    
    for spec in COMMAND_SPECS:
        if spec.category not in categories:
            categories[spec.category] = []
        categories[spec.category].append(spec.name)
    
    return categories


def get_system_prompt_commands() -> str:
    """
    Generate the AVAILABLE COMMANDS section for system prompt.
    
    Returns:
        Formatted string with all commands for LLM
    """
    categories = get_commands_by_category()
    
    lines = ["AVAILABLE COMMANDS (use these exact tokens)"]
    
    for category in ['Navigation', 'Interaction', 'Scanning', 'System']:
        if category not in categories:
            continue
            
        lines.append(f"\n{category.upper()}:")
        
        for spec in COMMAND_SPECS:
            if spec.category != category:
                continue
            
            # Format command with aliases
            cmd_line = f"  {spec.name}"
            if spec.syntax != spec.name:
                # Extract args from syntax
                args = spec.syntax[len(spec.name):].strip()
                if args:
                    cmd_line += f" {args}"
            
            lines.append(cmd_line)
            
            # Add aliases as comments
            for alias in spec.aliases:
                lines.append(f"  {alias}          # alias for {spec.name}")
    
    return "\n".join(lines)


def find_command_spec(command_name: str) -> CommandSpec:
    """
    Find command specification by name or alias.
    
    Args:
        command_name: Name or alias of command
    
    Returns:
        CommandSpec if found, None otherwise
    """
    command_name = command_name.lower()
    
    for spec in COMMAND_SPECS:
        if spec.name == command_name or command_name in spec.aliases:
            return spec
    
    return None


def get_all_command_names() -> List[str]:
    """
    Get list of all command names including aliases.
    
    Returns:
        List of all valid command names
    """
    names = []
    for spec in COMMAND_SPECS:
        names.append(spec.name)
        names.extend(spec.aliases)
    return names