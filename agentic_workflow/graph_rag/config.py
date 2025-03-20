"""
Graph RAG configuration - Default configuration settings for the Graph RAG system.

This module provides default configuration values and utilities for managing
the Graph RAG system's settings.
"""

import os
from typing import Dict, Any

# Default configuration
DEFAULT_CONFIG = {
    # Model settings
    'api_model': 'gpt-4o',
    'gpt4_threads': 4,
    
    # Agent pipeline
    'agent_pipeline': ['query_decomposition', 'graph_retriever', 'reasoning'],
    
    # Schema cache settings
    'schema_cache_ttl': 86400,  # 24 hours in seconds
    'schema_cache_dir': os.path.join('agentic_workflow', 'graph_rag', 'schema', 'cache'),
    'force_schema_refresh': False,
    
    # Prompts
    'prompts_dir': os.path.join('prompts', 'graph_rag'),
    
    # Performance settings
    'max_examples_per_node': 5,
    'max_examples_per_relationship': 3,
    'max_common_queries': 10,
    
    # Database settings
    'db_retry_attempts': 3,
    'db_retry_delay': 2,  # seconds
    
    # Debug settings
    'debug': False,
    'trace_queries': False
}


def get_config(override_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get the configuration with optional overrides.
    
    Args:
        override_config: Optional dictionary with config values to override
        
    Returns:
        The complete configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    
    # Apply environment overrides
    env_overrides = {
        'api_model': os.environ.get('GRAPH_RAG_MODEL'),
        'debug': os.environ.get('GRAPH_RAG_DEBUG') in ('1', 'true', 'yes', 'True'),
        'trace_queries': os.environ.get('GRAPH_RAG_TRACE') in ('1', 'true', 'yes', 'True'),
        'schema_cache_ttl': int(os.environ.get('GRAPH_RAG_CACHE_TTL', 0)) or None,
        'force_schema_refresh': os.environ.get('GRAPH_RAG_REFRESH_SCHEMA') in ('1', 'true', 'yes', 'True')
    }
    
    # Only update config with non-None environment values
    for key, value in env_overrides.items():
        if value is not None:
            config[key] = value
    
    # Apply explicit overrides
    if override_config:
        config.update(override_config)
    
    return config