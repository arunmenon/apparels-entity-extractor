#!/usr/bin/env python3
"""
Test Graph Retriever Agent

This script isolates and tests the GraphRetrieverAgent to verify that it correctly:
1. Connects to the database properly
2. Executes Cypher queries correctly
3. Formats the results properly

This helps identify if the issue is in the retrieval phase or elsewhere in the RAG pipeline.
"""

import os
import json
import logging
import sys
import time

# Fix import paths when running from any location
import sys
import os
# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from agentic_workflow.graph_rag.agents.graph_retriever import GraphRetrieverAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_graph_retrieval(test_queries, output_file="graph_retrieval_results.json"):
    """
    Test the graph retriever agent with various queries.
    
    Args:
        test_queries: List of test query dictionaries
        output_file: File to save the results
    """
    # Set environment variables if needed
    if not os.getenv("NEO4J_URI"):
        os.environ["NEO4J_URI"] = "neo4j://localhost:7687"
        os.environ["NEO4J_USER"] = "neo4j"
        os.environ["NEO4J_PASSWORD"] = "Rathum12!"
    
    # Initialize the graph retriever agent
    logger.info("Initializing GraphRetrieverAgent...")
    agent = GraphRetrieverAgent()
    
    results = []
    
    # Process each query
    for idx, query_item in enumerate(test_queries, 1):
        question = query_item.get('question', f'Test query {idx}')
        query_plan = query_item.get('query_plan', [])
        
        logger.info(f"\n[{idx}/{len(test_queries)}] Testing graph retrieval for: {question}")
        
        if not query_plan:
            logger.warning("No query plan provided, skipping")
            continue
        
        # Create input data for the agent
        input_data = {
            "original_question": question,
            "query_plan": query_plan
        }
        
        # Process the query plan
        start_time = time.time()
        result = agent.process(input_data)
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"Query execution completed in {processing_time:.2f} seconds")
        
        # Record result
        retrieval_data = {
            'question': question,
            'processing_time': processing_time,
            'query_plan': query_plan,
            'retrieved_context': result.get('retrieved_context', []),
            'error': result.get('error', None)
        }
        
        results.append(retrieval_data)
        
        # Display the retrieved context
        logger.info("=== RETRIEVAL RESULTS ===")
        retrieved_context = result.get('retrieved_context', [])
            
        for i, context_item in enumerate(retrieved_context, 1):
            purpose = context_item.get('purpose', 'Unknown purpose')
            cypher = context_item.get('cypher', 'No query')
            result_count = context_item.get('result_count', 0)
            error = context_item.get('error', None)
            
            logger.info(f"Result {i}: {purpose}")
            logger.info(f"Cypher: {cypher}")
            logger.info(f"Result count: {result_count}")
            
            if error:
                logger.error(f"Error: {error}")
            else:
                if result_count > 0:
                    context_result = context_item.get('result', [])
                    sample = context_result[0] if context_result else 'No results'
                    logger.info(f"Sample result: {sample}")
        
        logger.info("-" * 80)
    
    # Save all results
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test results saved to {output_file}")
    return results

if __name__ == "__main__":
    # Define test queries for different scenarios
    test_queries = [
        # Basic node retrieval
        {
            "question": "What compliance areas exist in the system?",
            "query_plan": [
                {
                    "purpose": "Retrieve all compliance areas",
                    "cypher": "MATCH (ca:ComplianceArea) RETURN ca.name AS name"
                }
            ]
        },
        # Basic relationship retrieval
        {
            "question": "What regulations apply to Apparel products?",
            "query_plan": [
                {
                    "purpose": "Find regulations for Apparel products",
                    "cypher": "MATCH (pc:ProductCategory {name: 'Apparel'})-[:HAS_COMPLIANCE_AREA]->(ca:ComplianceArea)-[:HAS_REGULATION]->(reg:Regulation) RETURN ca.name AS area, reg.name AS regulation, reg.citation AS citation"
                }
            ]
        },
        # Schema query
        {
            "question": "What node types exist in the database?",
            "query_plan": [
                {
                    "purpose": "Get all node labels in the database",
                    "cypher": "CALL db.labels() YIELD label RETURN label"
                }
            ]
        },
        # Relationship query
        {
            "question": "What relationship types exist in the database?",
            "query_plan": [
                {
                    "purpose": "Get all relationship types in the database",
                    "cypher": "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
                }
            ]
        },
        # Complex query
        {
            "question": "What are the most regulated product categories?",
            "query_plan": [
                {
                    "purpose": "Count regulations per product category",
                    "cypher": "MATCH (pc:ProductCategory)-[:HAS_COMPLIANCE_AREA]->(ca:ComplianceArea)-[:HAS_REGULATION]->(reg:Regulation) RETURN pc.name AS product_category, count(DISTINCT reg) AS regulation_count ORDER BY regulation_count DESC"
                }
            ]
        }
    ]
    
    # Run the test
    test_graph_retrieval(test_queries)