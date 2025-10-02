"""
Core browser automation package.
Exports base agent, mixins, and utilities.
"""

from .base_agent import BaseBrowserAgent, console
from .navigation import NavigationMixin
from .interaction import InteractionMixin
from .scanning import ScanningMixin

__all__ = [
    'BaseBrowserAgent',
    'NavigationMixin',
    'InteractionMixin',
    'ScanningMixin',
    'console'
]