#!/usr/bin/env python3
"""
Test script to verify that the Graph RAG system can now handle queries about
high-confidence MAY_VIOLATE relationships correctly.
"""

import json
import logging
import os
from agentic_workflow.graph_rag.agents.query_decomposition import QueryDecompositionAgent
from agentic_workflow.graph_rag.schema.schema_manager import schema_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_confidence_query():
    """Test that queries about high confidence relationships work correctly."""
    
    # Ensure schema is refreshed with latest metadata
    schema = schema_manager.get_formatted_schema(force_refresh=True)
    rich_context = schema_manager.get_formatted_rich_context(force_refresh=True)
    
    # Create a query decomposition agent
    agent = QueryDecompositionAgent()
    
    # Test queries that should use the correct confidence threshold
    test_queries = [
        "What are high confidence MAY_VIOLATE relationships?",
        "Show me products with high confidence of violating regulations",
        "List products with significant risk of violating weapon subcategories"
    ]
    
    results = []
    
    for query in test_queries:
        logger.info(f"Testing query: {query}")
        
        # Use the query decomposition agent to generate a Cypher query
        decomposed = agent.process({'question': query})
        
        # Check if the query includes MAY_VIOLATE and the correct threshold
        success = False
        threshold_correct = False
        
        if decomposed and 'query_plan' in decomposed:
            for plan in decomposed['query_plan']:
                cypher = plan.get('cypher', '')
                if 'MAY_VIOLATE' in cypher and 'confidence_score' in cypher:
                    success = True
                    # Check if using the threshold from metadata (0.4) and not a hardcoded value
                    if '>= 0.4' in cypher:
                        threshold_correct = True
        
        results.append({
            'query': query,
            'success': success,
            'threshold_correct': threshold_correct,
            'decomposition': decomposed
        })
        
        logger.info(f"  MAY_VIOLATE used: {success}")
        logger.info(f"  Correct threshold: {threshold_correct}")
    
    # Save results to a file
    with open('confidence_query_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Saved test results to confidence_query_test_results.json")
    
    # Return True if all tests passed
    all_succeeded = all(r['success'] and r['threshold_correct'] for r in results)
    return all_succeeded

if __name__ == "__main__":
    success = test_confidence_query()
    logger.info(f"Confidence query test {'SUCCESS' if success else 'FAILED'}")