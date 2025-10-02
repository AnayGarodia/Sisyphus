"""
Command registration system.
"""

from .registry import build_command_registry, get_command_help

__all__ = ['build_command_registry', 'get_command_help']