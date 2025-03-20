"""
Test for the refactored Graph RAG components.

This tests ensure that:
1. The new architecture with Agent and WorkflowManager works correctly
2. GraphRAGAgent can process questions and generate answers
3. Configuration and schema management work correctly
"""

import unittest
import logging
import os
from unittest.mock import patch, MagicMock

from ...agent_base import Agent
from ...workflow_manager import WorkflowManager
from ..agents.rag_orchestrator import GraphRAGAgent
from ..config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAgentImpl(Agent):
    """Implementation of Agent base class for testing."""
    
    def __init__(self, name, return_value=None):
        super().__init__(name=name)
        self.return_value = return_value
        self.execute_called = False
        self.last_data = None
        self.last_context = None
    
    def execute(self, data, context):
        self.execute_called = True
        self.last_data = data
        self.last_context = context
        return self.return_value or data


class TestWorkflowManager(unittest.TestCase):
    """Test the WorkflowManager component."""
    
    def test_workflow_initialization(self):
        """Test that WorkflowManager initializes correctly."""
        workflow = WorkflowManager(name="test_workflow")
        self.assertEqual(workflow.name, "test_workflow")
        self.assertEqual(len(workflow.agents), 0)
        self.assertEqual(workflow.agent_pipeline, [])
    
    def test_add_agent(self):
        """Test that agents can be added to the workflow."""
        workflow = WorkflowManager()
        agent = TestAgentImpl(name="test_agent")
        
        # Add the agent
        workflow.add_agent(agent)
        
        # Check that the agent was added
        self.assertIn("test_agent", workflow.agents)
        self.assertIn("test_agent", workflow.agent_pipeline)
        self.assertEqual(workflow.agents["test_agent"], agent)
    
    def test_run_pipeline(self):
        """Test that the workflow runs agents in sequence."""
        workflow = WorkflowManager()
        
        # Create agents with different return values
        agent1 = TestAgentImpl(name="agent1", return_value={"step1": "done", "question": "test"})
        agent2 = TestAgentImpl(name="agent2", return_value={"step1": "done", "step2": "done", "question": "test"})
        agent3 = TestAgentImpl(name="agent3", return_value={"step1": "done", "step2": "done", "step3": "done", "question": "test"})
        
        # Add agents to workflow
        workflow.add_agent(agent1)
        workflow.add_agent(agent2)
        workflow.add_agent(agent3)
        
        # Run the pipeline
        result = workflow.run_pipeline({"question": "test"})
        
        # Check that all agents were called
        self.assertTrue(agent1.execute_called)
        self.assertTrue(agent2.execute_called)
        self.assertTrue(agent3.execute_called)
        
        # Check that the final result includes all steps
        self.assertIn("step1", result)
        self.assertIn("step2", result)
        self.assertIn("step3", result)
        self.assertEqual(result["step3"], "done")


class TestGraphRAGAgent(unittest.TestCase):
    """Test the refactored GraphRAGAgent."""
    
    @patch('agentic_workflow.graph_rag.agents.rag_orchestrator.schema_manager')
    def test_initialization(self, mock_schema_manager):
        """Test that GraphRAGAgent initializes correctly."""
        # Mock schema_manager.get_schema to avoid actual DB calls
        mock_schema_manager.get_schema.return_value = {"nodes": [], "relationships": []}
        
        # Initialize with custom config
        agent = GraphRAGAgent(
            config_override={
                'api_model': 'gpt-4-test',
                'agent_pipeline': ['test_agent']
            },
            preload_schema=True
        )
        
        # Check that agent was initialized correctly
        self.assertEqual(agent.name, "graph_rag_agent")
        self.assertEqual(agent.config['api_model'], 'gpt-4-test')
        self.assertEqual(agent.config['agent_pipeline'], ['test_agent'])
        
        # Verify schema was preloaded
        mock_schema_manager.get_schema.assert_called_once()
    
    @patch('agentic_workflow.graph_rag.agents.rag_orchestrator.schema_manager')
    def test_execute(self, mock_schema_manager):
        """Test that execute method works correctly."""
        # Mock schema_manager.get_schema to avoid actual DB calls
        mock_schema_manager.get_schema.return_value = {"nodes": [], "relationships": []}
        
        # Create agent with mocked sub-agents
        agent = GraphRAGAgent(preload_schema=False)
        
        # Replace workflow's run_pipeline with a mock
        agent.workflow.run_pipeline = MagicMock(return_value={
            "answer": "Test answer",
            "reasoning": "Test reasoning",
            "evidence": ["Evidence 1"],
            "confidence": 0.9
        })
        
        # Call execute
        result = agent.execute({"question": "test question"}, {})
        
        # Verify that process_question was called with input
        agent.workflow.run_pipeline.assert_called_once()
        self.assertEqual(result["answer"], "Test answer")
        self.assertEqual(result["confidence"], 0.9)
    
    @patch('agentic_workflow.graph_rag.agents.rag_orchestrator.schema_manager')
    def test_process_question(self, mock_schema_manager):
        """Test that process_question method works correctly."""
        # Mock schema_manager.get_schema to avoid actual DB calls
        mock_schema_manager.get_schema.return_value = {"nodes": [], "relationships": []}
        
        # Create agent with mocked run method
        agent = GraphRAGAgent(preload_schema=False)
        agent.run = MagicMock(return_value={
            "answer": "Test answer",
            "reasoning": "Test reasoning",
            "evidence": ["Evidence 1"],
            "confidence": 0.9
        })
        
        # Call process_question
        result = agent.process_question("test question")
        
        # Verify run was called with wrapped question
        agent.run.assert_called_with({"question": "test question"})
        
        # Check result
        self.assertEqual(result["answer"], "Test answer")
        self.assertIn("processing_time", result)
    
    @patch('agentic_workflow.graph_rag.agents.rag_orchestrator.schema_manager')
    def test_refresh_schema(self, mock_schema_manager):
        """Test that refresh_schema method works correctly."""
        # Mock schema_manager.get_schema
        mock_schema_manager.get_schema.return_value = {"nodes": [], "relationships": []}
        
        # Create agent
        agent = GraphRAGAgent(preload_schema=False)
        
        # Call refresh_schema
        result = agent.refresh_schema()
        
        # Verify schema_manager.get_schema was called with force_refresh=True
        mock_schema_manager.get_schema.assert_called_with(force_refresh=True)
        self.assertTrue(result)
    
    def test_config(self):
        """Test that configuration system works correctly."""
        # Get default config
        config = get_config()
        
        # Check that default values are set
        self.assertEqual(config['api_model'], 'gpt-4o')
        self.assertEqual(len(config['agent_pipeline']), 3)
        
        # Test with overrides
        custom_config = get_config({'api_model': 'custom-model', 'debug': True})
        self.assertEqual(custom_config['api_model'], 'custom-model')
        self.assertTrue(custom_config['debug'])


if __name__ == '__main__':
    unittest.main()