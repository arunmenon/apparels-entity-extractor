"""
Reasoning Agent - Generates answers from graph data and query results.

This agent is responsible for:
1. Analyzing information retrieved from the graph database
2. Reasoning over the graph context to answer questions
3. Generating comprehensive answers with evidence and confidence scores
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

from ...agent_base import Agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReasoningAgent(Agent):
    """Agent that reasons over retrieved graph context to answer questions."""
    
    def __init__(self, system_prompt_path: str = None, reasoning_prompt_path: str = None):
        """
        Initialize the reasoning agent.
        
        Args:
            system_prompt_path: Path to system prompt for the LLM
            reasoning_prompt_path: Path to reasoning prompt for the LLM
        """
        super().__init__()
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'reasoning_system_prompt.txt')
        self.reasoning_prompt_path = reasoning_prompt_path or os.path.join('prompts', 'reasoning_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.reasoning_prompt_path, 'r') as f:
            self.reasoning_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
    
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a graph reasoning specialist who analyzes information retrieved from a taxonomy knowledge graph.
Your task is to reason over the graph context and provide accurate, insightful answers to questions about product taxonomies and compliance.
You should explain your reasoning process and cite specific evidence from the graph to support your conclusions."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create reasoning prompt if it doesn't exist
        if not os.path.exists(self.reasoning_prompt_path):
            reasoning_prompt = """Reason over the following graph context to answer the original question.

ORIGINAL QUESTION:
{{original_question}}

GRAPH CONTEXT:
{{graph_context}}

First analyze the retrieved information and identify relevant facts and patterns.
Then reason step-by-step to develop an answer to the original question.
Be clear and concise in your explanation, and cite specific evidence from the graph results.
If the retrieved information is insufficient to answer the question completely, acknowledge the limitations and provide the best possible answer based on available data.

Return your answer in the following JSON format:
```json
{
  "answer": "Your detailed answer to the question",
  "reasoning": "Your step-by-step reasoning process",
  "evidence": ["Specific piece of evidence 1", "Specific piece of evidence 2", ...],
  "confidence": 0-1 (your confidence in the answer based on available evidence)
}
```"""
            
            with open(self.reasoning_prompt_path, 'w') as f:
                f.write(reasoning_prompt)
    
    def execute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core execution method for the reasoning agent.
        
        Args:
            data: Input data for this agent
            context: Shared workflow context
            
        Returns:
            Processed data with agent results
        """
        return self.process(data)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Process the retrieved graph context and generate an answer.
        
        Args:
            input_data: Dictionary containing retrieved graph context and original question
            
        Returns:
            Dictionary with the generated answer
        """
        logger.info("Reasoning over graph context to generate answer...")
        
        retrieved_context = input_data.get('retrieved_context', [])
        original_question = input_data.get('original_question', '')
        
        if not retrieved_context:
            return {
                'answer': 'I could not find any relevant information in the graph database to answer your question.',
                'reasoning': 'No graph context was retrieved for analysis.',
                'evidence': [],
                'confidence': 0.0,
                'original_question': original_question
            }
        
        # Format the retrieved context for the prompt
        formatted_context = []
        for item in retrieved_context:
            purpose = item.get('purpose', 'Unknown purpose')
            result = item.get('result', [])
            error = item.get('error', '')
            
            if error:
                formatted_context.append(f"Query Purpose: {purpose}\nError: {error}\n")
            else:
                formatted_context.append(f"Query Purpose: {purpose}\nResults: {json.dumps(result, indent=2)}\n")
        
        graph_context = "\n".join(formatted_context)
        
        # Fill the prompt template
        filled_prompt = (self.reasoning_prompt
                        .replace("{{original_question}}", original_question)
                        .replace("{{graph_context}}", graph_context))
        
        # Call the LLM for reasoning
        try:
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4o",  # Use appropriate model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": filled_prompt}
                ],
                temperature=0.3,  # Moderate temperature for reasoning
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the response
            reasoning_result = json.loads(llm_response.choices[0].message.content)
            
            return {
                'answer': reasoning_result.get('answer', ''),
                'reasoning': reasoning_result.get('reasoning', ''),
                'evidence': reasoning_result.get('evidence', []),
                'confidence': reasoning_result.get('confidence', 0.0),
                'original_question': original_question,
                'llm_reasoning': reasoning_result  # Include full LLM reasoning for transparency
            }
            
        except Exception as e:
            logger.error(f"Error in reasoning: {e}")
            
            return {
                'answer': 'I encountered an error while trying to reason about your question.',
                'reasoning': f'Error during reasoning process: {str(e)}',
                'evidence': [],
                'confidence': 0.0,
                'original_question': original_question,
                'error': str(e)
            }