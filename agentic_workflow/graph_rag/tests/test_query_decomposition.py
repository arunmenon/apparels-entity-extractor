#!/usr/bin/env python3
"""
Test Query Decomposition Agent

This script isolates and tests the QueryDecompositionAgent to verify that it correctly:
1. Retrieves the schema from the database
2. Formats the schema for the LLM prompt
3. Generates appropriate Cypher queries for different questions

This helps identify if the issue is in the decomposition phase or elsewhere in the RAG pipeline.
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

from agentic_workflow.graph_rag.agents.query_decomposition import QueryDecompositionAgent
from agentic_workflow.graph_rag.schema.schema_manager import schema_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_query_decomposition(questions, output_file="query_decomposition_results.json"):
    """
    Test the query decomposition agent with various questions.
    
    Args:
        questions: List of questions to test
        output_file: File to save the results
    """
    # Set environment variables if needed
    if not os.getenv("NEO4J_URI"):
        os.environ["NEO4J_URI"] = "neo4j://localhost:7687"
        os.environ["NEO4J_USER"] = "neo4j"
        os.environ["NEO4J_PASSWORD"] = "Rathum12!"
    
    # First verify that we can get the schema
    logger.info("Retrieving schema from database...")
    schema = schema_manager.get_schema()
    
    # Display schema statistics
    node_types = schema.get('node_types', {})
    rel_types = schema.get('relationship_types', {})
    relationships = schema.get('relationships', [])
    
    logger.info(f"Schema retrieved successfully:")
    logger.info(f"- {len(node_types)} node types: {', '.join(node_types.keys())}")
    logger.info(f"- {len(rel_types)} relationship types: {', '.join(rel_types.keys())}")
    logger.info(f"- {len(relationships)} relationship patterns")
    
    # Initialize the query decomposition agent
    logger.info("Initializing QueryDecompositionAgent...")
    agent = QueryDecompositionAgent()
    
    results = []
    
    # Process each question
    for idx, question in enumerate(questions, 1):
        logger.info(f"\n[{idx}/{len(questions)}] Testing question decomposition: {question}")
        
        # Create input data for the agent
        input_data = {"question": question}
        
        # Process the question
        start_time = time.time()
        result = agent.process(input_data)
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"Query decomposition completed in {processing_time:.2f} seconds")
        
        # Record result
        decomposition_data = {
            'question': question,
            'processing_time': processing_time,
            'query_plan': result.get('query_plan', []),
            'thought_process': result.get('thought_process', ''),
            'full_response': result.get('llm_decomposition', {})
        }
        
        results.append(decomposition_data)
        
        # Display the query plan
        logger.info("=== QUERY PLAN ===")
        query_plan = result.get('query_plan', [])
            
        for i, query in enumerate(query_plan, 1):
            logger.info(f"Query {i}: {query.get('purpose')}")
            logger.info(f"Cypher: {query.get('cypher')}")
        
        logger.info(f"Thought process: {result.get('thought_process', 'None provided')}")
        logger.info("-" * 80)
    
    # Save all results
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test results saved to {output_file}")
    return results

if __name__ == "__main__":
    # Define test questions specifically targeting different query patterns
    test_questions = [
        # Schema questions
        "What are all the node types in the database?",
        "What are all the relationship types in the database?",
        
        # Entity-level questions
        "What compliance areas exist in the system?",
        "List all product categories",
        
        # Relationship questions
        "What regulations apply to Apparel products?",
        "Which compliance areas are related to children's products?",
        
        # Complex questions
        "What are the most regulated product categories?",
        "Show me product categories without any compliance areas"
    ]
    
    if len(sys.argv) > 1:
        # Run with a single question from command line
        test_query_decomposition([sys.argv[1]], "single_decomposition_result.json")
    else:
        # Run the full test suite
        test_query_decomposition(test_questions)