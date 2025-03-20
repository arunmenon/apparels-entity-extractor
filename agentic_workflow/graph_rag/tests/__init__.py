"""
Graph RAG Test Suite

This package contains tests for the Graph RAG module components:

1. test_graph_rag_direct.py - Tests the complete end-to-end RAG workflow
2. test_query_decomposition.py - Tests the query decomposition component in isolation
3. test_graph_retriever.py - Tests the graph retrieval component in isolation
4. test_reasoning_agent.py - Tests the reasoning component in isolation

These tests verify that:
1. The entire workflow functions correctly from question to answer
2. Each component works correctly in isolation
3. No steps are being bypassed in the pipeline
4. Real data is being retrieved from the graph database
"""

# Version
__version__ = "0.1.0"