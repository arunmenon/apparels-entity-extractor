"""
Graph Retriever Agent - Executes queries against the graph database and retrieves results.

This agent is responsible for:
1. Connecting to the graph database
2. Executing Cypher queries
3. Processing and formatting the results
4. Validating and fixing queries before execution
"""

import logging
from typing import Dict, List, Any, Optional

from ...agent_base import Agent
from graph_db.graph_strategy_factory import GraphDatabaseFactory
from .query_validator import QueryValidator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphRetrieverAgent(Agent):
    """Agent that retrieves relevant information from the graph database."""
    
    def __init__(self):
        """Initialize the graph retriever agent."""
        super().__init__()
        self.graph_db = None
        self.query_validator = QueryValidator()
    
    def connect_to_database(self):
        """Connect to the Neo4j database."""
        logger.info("Connecting to graph database...")
        self.graph_db = GraphDatabaseFactory.create_graph_database_strategy()
        self.graph_db.connect()
        logger.info("Connected to graph database")
    
    def close_database(self):
        """Close the database connection."""
        if self.graph_db:
            self.graph_db.close()
            logger.info("Closed database connection")
    
    def execute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core execution method for the graph retriever agent.
        
        Args:
            data: Input data for this agent
            context: Shared workflow context
            
        Returns:
            Processed data with agent results
        """
        return self.process(data)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Process the decomposed queries and retrieve information from the graph.
        
        Args:
            input_data: Dictionary containing query plan and original question
            
        Returns:
            Dictionary with retrieved graph context
        """
        logger.info("Retrieving information from graph database...")
        
        query_plan = input_data.get('query_plan', [])
        original_question = input_data.get('original_question', '')
        
        if not query_plan:
            return {
                'retrieved_context': [],
                'error': 'No queries to execute',
                'original_question': original_question
            }
        
        try:
            # Connect to the database
            self.connect_to_database()
            
            # Execute each query in the plan
            retrieved_context = []
            for query_item in query_plan:
                purpose = query_item.get('purpose', 'Unknown purpose')
                cypher = query_item.get('cypher', '')
                
                if not cypher:
                    logger.warning(f"Empty Cypher query for purpose: {purpose}")
                    continue
                
                logger.info(f"Executing query for: {purpose}")
                
                try:
                    # Validate and fix the query before execution
                    fixed_cypher, is_valid, validation_message = self.query_validator.validate_and_fix(cypher)
                    
                    if validation_message:
                        logger.warning(f"Query validation message: {validation_message}")
                    
                    # Execute the query (fixed version if available)
                    result = self.graph_db.execute_query(fixed_cypher)
                    
                    # Format the result
                    formatted_result = {
                        'purpose': purpose,
                        'original_cypher': cypher,
                        'executed_cypher': fixed_cypher if fixed_cypher != cypher else cypher,
                        'was_modified': fixed_cypher != cypher,
                        'validation_message': validation_message,
                        'result': result,
                        'result_count': len(result) if result else 0
                    }
                    
                    retrieved_context.append(formatted_result)
                    
                except Exception as query_error:
                    logger.error(f"Error executing query: {query_error}")
                    retrieved_context.append({
                        'purpose': purpose,
                        'original_cypher': cypher,
                        'error': str(query_error),
                        'result': [],
                        'result_count': 0
                    })
            
            # Close the database connection
            self.close_database()
            
            return {
                'retrieved_context': retrieved_context,
                'original_question': original_question,
                'thought_process': input_data.get('thought_process', '')
            }
            
        except Exception as e:
            logger.error(f"Error in graph retrieval: {e}")
            self.close_database()  # Ensure connection is closed even on error
            
            return {
                'retrieved_context': [],
                'error': str(e),
                'original_question': original_question
            }