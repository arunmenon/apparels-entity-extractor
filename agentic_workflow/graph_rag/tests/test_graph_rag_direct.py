#!/usr/bin/env python3
"""
Direct Graph RAG Test - Test the complete Graph RAG workflow

This script tests the full Graph RAG pipeline:
1. Schema retrieval
2. Query decomposition 
3. Graph retrieval
4. Reasoning

This ensures we're not bypassing any part of the workflow and using all components
as they are intended to be used.
"""

import os
import json
import logging
import sys
import time
from typing import Dict, Any, List

# Fix import paths when running from any location
import sys
import os
# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from agentic_workflow.graph_rag.agents.rag_orchestrator import GraphRAGAgent
from agentic_workflow.graph_rag.schema.schema_manager import schema_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_graph_rag_with_questions(questions: List[str], output_file: str = "test_graph_rag_results.json"):
    """
    Test the Graph RAG agent with multiple questions and save results.
    
    Args:
        questions: List of questions to test
        output_file: File to save the results
    """
    # Set environment variables if needed
    if not os.getenv("NEO4J_URI"):
        os.environ["NEO4J_URI"] = "neo4j://localhost:7687"
        os.environ["NEO4J_USER"] = "neo4j"
        os.environ["NEO4J_PASSWORD"] = "Rathum12!"
    
    logger.info(f"Testing Graph RAG with {len(questions)} questions")
    
    # Initialize the Graph RAG agent
    agent = GraphRAGAgent(preload_schema=True)
    
    # Get the schema to verify connectivity
    schema = schema_manager.get_schema()
    logger.info(f"Connected to database. Schema has {len(schema.get('node_types', {}))} node types " 
                f"and {len(schema.get('relationship_types', {}))} relationship types")
    
    results = []
    
    # Process each question
    for idx, question in enumerate(questions, 1):
        logger.info(f"\n[{idx}/{len(questions)}] Testing question: {question}")
        
        # Process the question through the full RAG workflow
        start_time = time.time()
        result = agent.process_question(question)
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"Processing time: {processing_time:.2f} seconds")
        
        # Record workflow data for analysis
        workflow_data = {
            'question': question,
            'processing_time': processing_time,
            'query_plan': result.get('query_plan', []),
            'thought_process': result.get('thought_process', ''),
            'retrieved_context': result.get('retrieved_context', []),
            'answer': result.get('answer', ''),
            'reasoning': result.get('reasoning', ''),
            'evidence': result.get('evidence', []),
            'confidence': result.get('confidence', 0.0)
        }
        
        results.append(workflow_data)
        
        # Display the query plan
        logger.info("=== QUERY PLAN ===")
        query_plan = []
        
        # Extract query plan from LLM decomposition if available
        if 'llm_decomposition' in result:
            query_plan = result['llm_decomposition'].get('query_plan', [])
        else:
            query_plan = result.get('query_plan', [])
            
        for i, query in enumerate(query_plan, 1):
            logger.info(f"Query {i}: {query.get('purpose')}")
            logger.info(f"Cypher: {query.get('cypher')}")
        
        # Display the retrieved context
        logger.info("\n=== RETRIEVED CONTEXT ===")
        retrieved_context = result.get('retrieved_context', [])
        for i, context in enumerate(retrieved_context, 1):
            logger.info(f"Context {i}: {context.get('purpose')}")
            logger.info(f"Result count: {context.get('result_count', 0)}")
            if context.get('result') and len(context.get('result', [])) > 0:
                sample = context.get('result')[0]
                logger.info(f"Sample result: {sample}")
        
        # Display the answer
        logger.info("\n=== ANSWER ===")
        logger.info(f"Answer: {result.get('answer', '')}")
        logger.info(f"Confidence: {result.get('confidence', 0.0)}")
        logger.info("-" * 80)
    
    # Save all test results
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"All test results saved to {output_file}")
    return results

def test_single_question(question: str):
    """Test the Graph RAG agent with a single question."""
    return test_graph_rag_with_questions([question], "single_question_result.json")[0]

if __name__ == "__main__":
    # Define test questions
    test_questions = [
        "What compliance areas exist in the system?",
        "What are all the product categories in the database?",
        "What regulations apply to Apparel products?",
        "Which compliance areas are related to children's products?",
        "What are the restrictions for selling toys?",
        "Show me all relationship types between products and compliance areas"
    ]
    
    if len(sys.argv) > 1:
        # Run single question from command line
        question = sys.argv[1]
        test_single_question(question)
    else:
        # Run the full test suite
        test_graph_rag_with_questions(test_questions)