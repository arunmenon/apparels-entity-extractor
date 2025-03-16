"""
Graph RAG Agent - An agentic workflow for querying taxonomies in a graph database.

This module implements a REACT-pattern agentic workflow that:
1. Takes a natural language question about the taxonomy
2. Decomposes the question into graph queries
3. Retrieves relevant subgraphs from the graph database
4. Reasons over the retrieved context to generate an answer
5. Returns the answer with supporting evidence

Components:
- GraphRAGAgent: Main orchestrating agent
- QueryDecompositionAgent: Breaks down questions into graph queries
- GraphRetrieverAgent: Executes graph queries and retrieves context
- ReasoningAgent: Reasons over graph context to generate answers
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import time

from .agent_base import Agent
from .agent_workflow import AgentWorkflow
from graph_db.graph_strategy_factory import GraphDatabaseFactory

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

TAXONOMY SCHEMA:
- Product_Category: Categories of products (e.g., Apparel, Electronics)
  - Properties: name
- Compliance_Area: Areas of compliance for product categories
  - Properties: name
- Regulation: Specific regulations related to compliance areas
  - Properties: name, citation
- Standard: Industry standards related to compliance areas
  - Properties: name, citation
- Criterion: Specific compliance criteria
  - Properties: description
- Relationships:
  - (Product_Category)-[:HAS_COMPLIANCE_AREA]->(Compliance_Area)
  - (Compliance_Area)-[:HAS_REGULATION]->(Regulation)
  - (Compliance_Area)-[:HAS_STANDARD]->(Standard)
  - (Compliance_Area)-[:HAS_CRITERION]->(Criterion)
  - (Compliance_Area)-[:IMPACTS/OVERLAPS_WITH/RELATED_TO]->(Compliance_Area)

Step 1: Identify the key entities and relationships in the question.
Step 2: Formulate one or more Cypher queries to retrieve the relevant information.
Step 3: Ensure your queries are efficient and focused on the specific question asked.

For example, if the question is "What regulations apply to Apparel products?", you might generate:
```cypher
MATCH (cat:Product_Category {name: "Apparel"})-[:HAS_COMPLIANCE_AREA]->(area:Compliance_Area)
MATCH (area)-[:HAS_REGULATION]->(reg:Regulation)
RETURN cat.name as Category, area.name as ComplianceArea, reg.name as Regulation, reg.citation as Citation
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
        
        # Fill the prompt template
        filled_prompt = self.decomposition_prompt.replace("{{question}}", question)
        
        # Call the LLM for query decomposition
        try:
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4-turbo",  # Use appropriate model
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


class GraphRetrieverAgent(Agent):
    """Agent that retrieves relevant information from the graph database."""
    
    def __init__(self):
        """Initialize the graph retriever agent."""
        super().__init__()
        self.graph_db = None
    
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
                    # Execute the query
                    result = self.graph_db.execute_query(cypher)
                    
                    # Format the result
                    formatted_result = {
                        'purpose': purpose,
                        'cypher': cypher,
                        'result': result,
                        'result_count': len(result) if result else 0
                    }
                    
                    retrieved_context.append(formatted_result)
                    
                except Exception as query_error:
                    logger.error(f"Error executing query: {query_error}")
                    retrieved_context.append({
                        'purpose': purpose,
                        'cypher': cypher,
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
                model="gpt-4-turbo",  # Use appropriate model
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


class GraphRAGAgent(AgentWorkflow):
    """Main agent that orchestrates the graph RAG workflow using the REACT pattern."""
    
    def __init__(self, prompts_dir: str = None):
        """
        Initialize the Graph RAG agent.
        
        Args:
            prompts_dir: Directory containing LLM prompts (defaults to 'prompts')
        """
        super().__init__()
        
        # Set prompts directory
        self.prompts_dir = prompts_dir or 'prompts'
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
        
        # Add processing time information
        result['processing_time'] = end_time - start_time
        
        return result


# API endpoint definition
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Taxonomy Graph RAG API",
    description="API for querying taxonomy information using a graph RAG approach",
    version="1.0.0"
)

class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str
    reasoning: str
    evidence: List[str]
    confidence: float
    processing_time: float

# Initialize the Graph RAG agent
graph_rag_agent = GraphRAGAgent()

@app.post("/query", response_model=AnswerResponse)
async def query_taxonomy(request: QuestionRequest):
    """
    Query the taxonomy with a natural language question.
    
    Args:
        request: Object containing the question
        
    Returns:
        Object containing the answer and supporting information
    """
    try:
        result = graph_rag_agent.process_question(request.question)
        
        # Extract the relevant fields for the response
        response = {
            "answer": result.get("answer", ""),
            "reasoning": result.get("reasoning", ""),
            "evidence": result.get("evidence", []),
            "confidence": result.get("confidence", 0.0),
            "processing_time": result.get("processing_time", 0.0)
        }
        
        return response
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn agentic_workflow.graph_rag_agent:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agentic_workflow.graph_rag_agent:app", host="0.0.0.0", port=8000, reload=True)