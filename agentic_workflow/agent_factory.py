"""
Factory pattern implementation for creating agents in the workflow.

This module provides a factory for instantiating various types of agents
based on configuration or explicit requirements.
"""

import os
import importlib
from typing import Any, Dict, Type, Optional

from .agent_base import Agent


class AgentFactory:
    """
    Factory for creating instances of agents.
    
    This class implements the Factory pattern to instantiate appropriate
    agent classes based on configuration or type requirements.
    """
    
    _registry: Dict[str, Type[Agent]] = {}
    
    @classmethod
    def register(cls, agent_type: str, agent_class: Type[Agent]) -> None:
        """
        Register an agent class with the factory.
        
        Args:
            agent_type: A string identifier for the agent type
            agent_class: The agent class to register
        """
        cls._registry[agent_type] = agent_class
    
    @classmethod
    def create(cls, agent_type: str, config: Dict[str, Any] = None, **kwargs) -> Agent:
        """
        Create an instance of the specified agent type.
        
        Args:
            agent_type: The type of agent to create
            config: Configuration dict for agent initialization
            **kwargs: Additional keyword arguments to pass to the agent constructor
            
        Returns:
            An instance of the requested agent
            
        Raises:
            ValueError: If the agent type is not registered
        """
        if agent_type not in cls._registry:
            raise ValueError(f"Agent type '{agent_type}' is not registered")
        
        agent_class = cls._registry[agent_type]
        
        # Combine config dict with kwargs, with kwargs taking precedence
        init_args = {}
        if config:
            init_args.update(config)
        if kwargs:
            init_args.update(kwargs)
        
        return agent_class(**init_args)
    
    @classmethod
    def create_chain(cls, agent_types: list, config: Dict[str, Any] = None) -> Agent:
        """
        Create a chain of agents connected via the Chain of Responsibility pattern.
        
        Args:
            agent_types: List of agent types in processing order
            config: Configuration dict with settings for each agent type
            
        Returns:
            The first agent in the chain
            
        Raises:
            ValueError: If any agent type is not registered
        """
        if not agent_types:
            raise ValueError("Cannot create empty agent chain")
        
        # Create the first agent
        first_agent = cls.create(
            agent_types[0],
            config.get(agent_types[0]) if config else None
        )
        
        # Create remaining agents and chain them
        current_agent = first_agent
        for agent_type in agent_types[1:]:
            agent_config = config.get(agent_type) if config else None
            next_agent = cls.create(agent_type, agent_config)
            current_agent.set_next(next_agent)
            current_agent = next_agent
        
        return first_agent
    
    @classmethod
    def load_from_module(cls, module_path: str) -> None:
        """
        Dynamically load agent classes from a module and register them.
        
        This method enables plugin-like functionality by loading agent
        implementations from external modules.
        
        Args:
            module_path: Dotted path to the module containing agent classes
            
        Raises:
            ImportError: If the module cannot be imported
        """
        try:
            module = importlib.import_module(module_path)
            
            # Look for any Agent subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                try:
                    # Check if it's a class and a subclass of Agent (but not Agent itself)
                    if (isinstance(attr, type) and
                        issubclass(attr, Agent) and
                        attr is not Agent):
                        
                        # Get agent_type from class attribute or use class name
                        agent_type = getattr(attr, 'agent_type', attr_name.lower())
                        cls.register(agent_type, attr)
                except (TypeError, AttributeError):
                    # Not a class or not an Agent subclass
                    continue
                    
        except ImportError as e:
            raise ImportError(f"Failed to load agent module '{module_path}': {e}")


# Register built-in agent types
def register_builtin_agents():
    """Register the standard built-in agent types with the factory."""
    from .page_classifier import PageClassifierAgent
    from .entity_extractor import EntityExtractorAgent
    from .context_agent import ContextAgent
    from .cypher_generator import CypherGeneratorAgent
    
    # Register standard agents
    AgentFactory.register('classifier', PageClassifierAgent)
    AgentFactory.register('extractor', EntityExtractorAgent)
    AgentFactory.register('context', ContextAgent)
    AgentFactory.register('cypher', CypherGeneratorAgent)
    
    # Try to register Docling-based entity extractor if available
    try:
        from .docling_entity_extractor import DoclingEntityExtractor
        AgentFactory.register('docling_extractor', DoclingEntityExtractor)
        print("Docling entity extractor registered successfully.")
    except ImportError:
        print("Docling entity extractor not available. Install docling to enable advanced document processing.")


# Register built-in agents when this module is imported
register_builtin_agents()