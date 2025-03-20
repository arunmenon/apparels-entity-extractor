#!/usr/bin/env python3
"""
Test Reasoning Agent

This script isolates and tests the ReasoningAgent to verify that it correctly:
1. Takes retrieved context and generates appropriate answers
2. Provides reasoning and evidence citations
3. Accurately processes different types of context data

This helps identify if the issue is in the reasoning phase or elsewhere in the RAG pipeline.
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

from agentic_workflow.graph_rag.agents.reasoning import ReasoningAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_reasoning_agent(test_contexts, output_file="reasoning_test_results.json"):
    """
    Test the reasoning agent with various context scenarios.
    
    Args:
        test_contexts: List of test context dictionaries
        output_file: File to save the results
    """
    # Initialize the reasoning agent
    logger.info("Initializing ReasoningAgent...")
    agent = ReasoningAgent()
    
    results = []
    
    # Process each test context
    for idx, context_item in enumerate(test_contexts, 1):
        question = context_item.get('question', f'Test context {idx}')
        retrieved_context = context_item.get('retrieved_context', [])
        
        logger.info(f"\n[{idx}/{len(test_contexts)}] Testing reasoning for: {question}")
        
        if not retrieved_context:
            logger.warning("No context provided, skipping")
            continue
        
        # Create input data for the agent
        input_data = {
            "original_question": question,
            "retrieved_context": retrieved_context,
            "thought_process": context_item.get('thought_process', '')
        }
        
        # Process the context
        start_time = time.time()
        result = agent.process(input_data)
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"Reasoning completed in {processing_time:.2f} seconds")
        
        # Record result
        reasoning_data = {
            'question': question,
            'processing_time': processing_time,
            'retrieved_context': retrieved_context,
            'answer': result.get('answer', ''),
            'reasoning': result.get('reasoning', ''),
            'evidence': result.get('evidence', []),
            'confidence': result.get('confidence', 0.0),
            'full_response': result.get('llm_reasoning', {})
        }
        
        results.append(reasoning_data)
        
        # Display the results
        logger.info("=== REASONING RESULTS ===")
        logger.info(f"Answer: {result.get('answer', '')}")
        logger.info(f"Confidence: {result.get('confidence', 0.0)}")
        logger.info(f"Reasoning: {result.get('reasoning', '')}")
        
        evidence = result.get('evidence', [])
        if evidence:
            logger.info("Evidence:")
            for i, evidence_item in enumerate(evidence, 1):
                logger.info(f"  {i}. {evidence_item}")
                
        logger.info("-" * 80)
    
    # Save all results
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test results saved to {output_file}")
    return results

if __name__ == "__main__":
    # Define test contexts with different scenarios
    test_contexts = [
        # Simple query with results
        {
            "question": "What compliance areas exist in the system?",
            "retrieved_context": [
                {
                    "purpose": "Retrieve all compliance areas",
                    "cypher": "MATCH (ca:ComplianceArea) RETURN ca.name AS name",
                    "result": [
                        {"name": "Safety"},
                        {"name": "Environmental"},
                        {"name": "Labeling"},
                        {"name": "Children's Products"}
                    ],
                    "result_count": 4
                }
            ]
        },
        # Relationship query with results
        {
            "question": "What regulations apply to Apparel products?",
            "retrieved_context": [
                {
                    "purpose": "Find regulations for Apparel products",
                    "cypher": "MATCH (pc:ProductCategory {name: 'Apparel'})-[:HAS_COMPLIANCE_AREA]->(ca:ComplianceArea)-[:HAS_REGULATION]->(reg:Regulation) RETURN ca.name AS area, reg.name AS regulation, reg.citation AS citation",
                    "result": [
                        {"area": "Safety", "regulation": "Flammability Standard", "citation": "16 CFR 1610"},
                        {"area": "Labeling", "regulation": "Textile Fiber Products Identification Act", "citation": "15 U.S.C. 70"}
                    ],
                    "result_count": 2
                }
            ]
        },
        # Query with no results
        {
            "question": "What restrictions apply to electronic toys?",
            "retrieved_context": [
                {
                    "purpose": "Find restrictions for electronic toys",
                    "cypher": "MATCH (pc:ProductCategory {name: 'Toys'})-[:HAS_SUBCATEGORY]->(sc:ProductSubcategory {name: 'Electronic Toys'})-[:HAS_RESTRICTION]->(r:Restriction) RETURN r.name AS restriction, r.description AS description",
                    "result": [],
                    "result_count": 0
                }
            ]
        },
        # Query with error
        {
            "question": "What hazardous materials are regulated in children's products?",
            "retrieved_context": [
                {
                    "purpose": "Find hazardous materials regulations for children's products",
                    "cypher": "MATCH (pc:ProductCategory)-[:HAS_COMPLIANCE_AREA]->(:ComplianceArea {name: 'Children\\'s Products'})-[:REGULATES]->(hm:HazardousMaterial) RETURN pc.name AS product, hm.name AS hazardous_material, hm.limit AS limit",
                    "error": "Relationship type REGULATES does not exist in the database",
                    "result": [],
                    "result_count": 0
                }
            ]
        },
        # Multiple query results
        {
            "question": "Tell me about product categories and their compliance areas",
            "retrieved_context": [
                {
                    "purpose": "List all product categories",
                    "cypher": "MATCH (pc:ProductCategory) RETURN pc.name AS name",
                    "result": [
                        {"name": "Apparel"},
                        {"name": "Toys"},
                        {"name": "Furniture"},
                        {"name": "Electronics"}
                    ],
                    "result_count": 4
                },
                {
                    "purpose": "Get compliance areas for each product category",
                    "cypher": "MATCH (pc:ProductCategory)-[:HAS_COMPLIANCE_AREA]->(ca:ComplianceArea) RETURN pc.name AS product, collect(ca.name) AS compliance_areas",
                    "result": [
                        {"product": "Apparel", "compliance_areas": ["Safety", "Labeling"]},
                        {"product": "Toys", "compliance_areas": ["Safety", "Children's Products"]}
                    ],
                    "result_count": 2
                }
            ]
        }
    ]
    
    # Run the test
    test_reasoning_agent(test_contexts)