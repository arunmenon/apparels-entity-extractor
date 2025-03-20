"""
Query Decomposition Agent - Converts natural language questions into Neo4j Cypher queries.

This agent is responsible for:
1. Analyzing questions about the graph data
2. Breaking down complex questions into graph queries
3. Generating Cypher queries to retrieve relevant information
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

from ...agent_base import Agent
from ..schema.schema_manager import schema_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QueryDecompositionAgent(Agent):
    """Agent that decomposes natural language questions into graph queries."""
    
    def __init__(self, system_prompt_path: str = None, decomposition_prompt_path: str = None):
        """
        Initialize the query decomposition agent.
        
        Args:
            system_prompt_path: Path to system prompt for the LLM
            decomposition_prompt_path: Path to decomposition prompt for the LLM
        """
        super().__init__()
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'query_decomposition_system_prompt.txt')
        self.decomposition_prompt_path = decomposition_prompt_path or os.path.join('prompts', 'query_decomposition_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.decomposition_prompt_path, 'r') as f:
            self.decomposition_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
    
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a query decomposition specialist focused on converting natural language questions into graph database queries.
Your task is to analyze a question about a taxonomy and break it down into specific graph queries that can retrieve the relevant information.
You will identify entities, relationships, and constraints in the question and translate them into appropriate Cypher queries for Neo4j."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create decomposition prompt if it doesn't exist
        if not os.path.exists(self.decomposition_prompt_path):
            decomposition_prompt = """Analyze the following question about a product taxonomy and decompose it into Neo4j Cypher queries.

QUESTION:
{{question}}

{{schema}}

Step 1: Identify the key entities and relationships in the question.
Step 2: Look at the provided schema and examples to understand the data structure.
Step 3: Review the common queries for similar patterns you can adapt.
Step 4: Formulate one or more Cypher queries to retrieve the relevant information.
Step 5: Ensure your queries are efficient and focused on the specific question asked.

IMPORTANT GUIDELINES:
- Use the actual node labels and relationship types from the schema
- Reference the node examples to understand what properties are available
- Look at the relationship examples to understand how entities connect
- Adapt the common queries where possible instead of creating queries from scratch
- Focus on retrieving only the data needed to answer the question
- Include properties in your query that will be helpful for the final answer

For example, if the question is "What regulations apply to Apparel products?", you might generate:
```cypher
MATCH (pc:ProductCategory {name: "Apparel"})-[:REGULATED_UNDER]->(reg:Law_Regulation)
RETURN pc.name as Category, reg.id as RegulationID, reg.name as Regulation, reg.description as Description
```

Return a JSON object with the following structure:
```json
{
  "query_plan": [
    {
      "purpose": "Description of what this query retrieves",
      "cypher": "The Cypher query"
    },
    ...
  ],
  "thought_process": "Explanation of your reasoning and how these queries will help answer the question"
}
```"""
            
            with open(self.decomposition_prompt_path, 'w') as f:
                f.write(decomposition_prompt)
    
    def execute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core execution method for the query decomposition agent.
        
        Args:
            data: Input data for this agent
            context: Shared workflow context
            
        Returns:
            Processed data with agent results
        """
        return self.process(data)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Process the input question and decompose it into graph queries.
        
        Args:
            input_data: Dictionary containing the user's question
            
        Returns:
            Dictionary with decomposed queries
        """
        logger.info("Decomposing question into graph queries...")
        
        question = input_data.get('question', '')
        if not question:
            return {
                'query_plan': [],
                'error': 'No question provided'
            }
        
        # Get the current schema and rich context from the schema manager
        schema_text = schema_manager.get_formatted_schema()
        rich_context_text = schema_manager.get_formatted_rich_context()
        
        # Combine schema and rich context for a more comprehensive prompt
        combined_context = f"{schema_text}\n\n{rich_context_text}"
        
        # Fill the prompt template
        filled_prompt = self.decomposition_prompt.replace("{{question}}", question).replace("{{schema}}", combined_context)
        
        # Call the LLM for query decomposition
        try:
            logger.info("Calling LLM for query decomposition...")
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4o",  # Use appropriate model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": filled_prompt}
                ],
                temperature=0.2,  # Low temperature for more deterministic results
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the response
            decomposition_result = json.loads(llm_response.choices[0].message.content)
            query_plan = decomposition_result.get('query_plan', [])
            thought_process = decomposition_result.get('thought_process', '')
            
            logger.info(f"Query decomposition complete. Generated {len(query_plan)} queries.")
            
            return {
                'query_plan': query_plan,
                'thought_process': thought_process,
                'original_question': question,
                'llm_decomposition': decomposition_result  # Include full LLM response for transparency
            }
            
        except Exception as e:
            logger.error(f"Error in query decomposition: {e}")
            return {
                'query_plan': [],
                'error': str(e),
                'original_question': question
            }