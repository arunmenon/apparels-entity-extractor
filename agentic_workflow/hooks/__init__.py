"""
Hook implementations for the agentic workflow.

This package contains observers and hooks that can be attached to
the workflow to extend its functionality.
"""

# Import for direct access
from .validation import ValidationObserver
from .statistics import StatisticsObserver