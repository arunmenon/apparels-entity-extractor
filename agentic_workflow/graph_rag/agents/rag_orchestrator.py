"""
Graph RAG Orchestrator - Main orchestration agent for the Graph RAG workflow.

This agent is responsible for:
1. Coordinating the entire graph RAG workflow
2. Managing the sequence of agent interactions
3. Processing questions from end to end
4. Managing schema refreshing and caching
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional

from ...agent_base import Agent
from ...workflow_manager import WorkflowManager
from .query_decomposition import QueryDecompositionAgent
from .graph_retriever import GraphRetrieverAgent
from .reasoning import ReasoningAgent
from ..schema.schema_manager import schema_manager
from ..config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphRAGAgent(Agent):
    """Main agent that orchestrates the graph RAG workflow using the REACT pattern."""
    
    def __init__(self, config_override: Dict[str, Any] = None, preload_schema: bool = True):
        """
        Initialize the Graph RAG agent.
        
        Args:
            config_override: Optional configuration overrides
            preload_schema: Whether to preload the graph schema during initialization
        """
        # Initialize base Agent with name
        super().__init__(name="graph_rag_agent")
        
        # Get configuration
        self.config = get_config(config_override)
        
        # Initialize workflow manager
        self.workflow = WorkflowManager(name="graph_rag", config=self.config)
        
        # Set prompts directory
        self.prompts_dir = self.config.get('prompts_dir', os.path.join('prompts', 'graph_rag'))
        os.makedirs(self.prompts_dir, exist_ok=True)
        
        # Prepare prompt paths
        decomposition_system_prompt = os.path.join(self.prompts_dir, 'query_decomposition_system_prompt.txt')
        decomposition_prompt = os.path.join(self.prompts_dir, 'query_decomposition_prompt.txt')
        
        reasoning_system_prompt = os.path.join(self.prompts_dir, 'reasoning_system_prompt.txt')
        reasoning_prompt = os.path.join(self.prompts_dir, 'reasoning_prompt.txt')
        
        # Create the component agents
        self.query_decomposition = QueryDecompositionAgent(
            system_prompt_path=decomposition_system_prompt,
            decomposition_prompt_path=decomposition_prompt
        )
        
        self.graph_retriever = GraphRetrieverAgent()
        
        self.reasoning_agent = ReasoningAgent(
            system_prompt_path=reasoning_system_prompt,
            reasoning_prompt_path=reasoning_prompt
        )
        
        # Configure the workflow
        self.add_agent(self.query_decomposition)
        self.add_agent(self.graph_retriever)
        self.add_agent(self.reasoning_agent)
        
        # Preload schema information if requested
        if preload_schema:
            logger.info("Preloading graph schema information...")
            try:
                # This will trigger schema retrieval and caching
                force_refresh = self.config.get('force_schema_refresh', False)
                schema_manager.get_schema(force_refresh=force_refresh)
                logger.info("Graph schema preloaded successfully")
            except Exception as e:
                logger.warning(f"Failed to preload graph schema: {e}. Will try again on first query.")
    
    def add_agent(self, agent):
        """
        Add an agent to the workflow.
        
        Args:
            agent: The agent to add to the workflow
            
        Returns:
            The added agent for method chaining
        """
        return self.workflow.add_agent(agent)
    
    def execute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core execution method required by Agent base class.
        
        Args:
            data: Input data for this agent (contains 'question')
            context: Shared workflow context
            
        Returns:
            Processed data with agent results
        """
        # Extract question if present, or use empty string
        question = data.get('question', '')
        
        # Generate response for the question
        return self.process_question(question)
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the workflow with the given input data.
        
        Args:
            input_data: The input data to process through the workflow
            
        Returns:
            The result of the workflow
        """
        # Delegate to the workflow manager
        return self.workflow.run_pipeline(input_data)
    
    def process_question(self, question: str) -> Dict:
        """
        Process a user question and generate an answer.
        
        Args:
            question: The user's natural language question
            
        Returns:
            Dictionary with the answer and supporting information
        """
        # Wrap the question in the expected input format
        input_data = {'question': question}
        
        # Run the workflow
        start_time = time.time()
        result = self.run(input_data)
        end_time = time.time()
        
        # Add processing time information if not already added by workflow
        if 'processing_time' not in result:
            result['processing_time'] = end_time - start_time
        
        return result
        
    def refresh_schema(self) -> bool:
        """
        Force a refresh of the graph schema information.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        try:
            logger.info("Forcing refresh of graph schema...")
            # Force schema refresh through the schema manager
            schema_manager.get_schema(force_refresh=True)
            logger.info("Graph schema refreshed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh graph schema: {e}")
            return False
    
    def register_hook(self, hook_point: str, hook_function):
        """
        Register a hook function to be called at a specific point in the workflow.
        
        Args:
            hook_point: The point in the workflow to call the hook
            hook_function: A function to call at the specified hook point
            
        Returns:
            bool: True if hook was registered, False otherwise
        """
        return self.workflow.register_hook(hook_point, hook_function)