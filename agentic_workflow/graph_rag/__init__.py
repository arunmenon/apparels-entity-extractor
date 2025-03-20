"""
Graph RAG Package - A modular implementation of a Graph Retrieval-Augmented Generation system.

This package provides:
1. A complete RAG workflow optimized for graph databases
2. Dynamic schema awareness for graph-based question answering
3. FastAPI endpoints for integration with other services
4. Intelligent query decomposition and reasoning
5. Efficient schema caching and rich context building

Main components:
- QueryDecompositionAgent: Breaks down questions into graph queries
- GraphRetrieverAgent: Executes graph queries and retrieves context
- ReasoningAgent: Reasons over graph context to generate answers
- GraphRAGAgent: Main orchestrating agent for the workflow
- SchemaManager: Manages graph schema information and caching
"""

# Agent components
from .agents.query_decomposition import QueryDecompositionAgent
from .agents.graph_retriever import GraphRetrieverAgent
from .agents.reasoning import ReasoningAgent
from .agents.rag_orchestrator import GraphRAGAgent

# Schema management
from .schema.schema_manager import schema_manager

# Configuration
from .config import get_config, DEFAULT_CONFIG

# Import API app for direct use
from .api.endpoints import app as api_app

# Version information
__version__ = "0.2.0"

__all__ = [
    # Agent components
    'QueryDecompositionAgent',
    'GraphRetrieverAgent',
    'ReasoningAgent',
    'GraphRAGAgent',
    
    # Schema management
    'schema_manager',
    
    # Configuration
    'get_config',
    'DEFAULT_CONFIG',
    
    # API
    'api_app'
]