import os
import json
import requests
import time
import sys

class CypherGeneratorAgent:
    """
    Agent 4: Cypher Query Generation
    
    Generates Neo4j Cypher queries from the extracted entity data.
    Uses LLM to generate optimal queries rather than procedural generation.
    """
    
    def __init__(self, api_key=None, model=None, prompt_path="prompts/cypher_generator_prompt.txt"):
        """Initialize the Cypher Generator with API credentials and prompts."""
        # Set up API key and model
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.model = model or os.getenv('OPENAI_MODEL', 'gpt-4o')
        
        # Load prompt
        try:
            with open(prompt_path, "r") as f:
                self.system_prompt = f.read()
        except Exception as e:
            print(f"Warning: Could not load Cypher generator prompt from {prompt_path}: {e}")
            self.system_prompt = "Generate a Neo4j Cypher query from the given entity data."
    
    def build_cypher(self, context):
        """
        Generate a comprehensive Cypher query from the full entity context.
        
        Args:
            context: The full entity context from ContextAgent
            
        Returns:
            A JSON object with a "cypher_query" field containing the Neo4j query.
        """
        # Create a structured representation of all entities for the LLM
        prompt_data = self._format_context_for_prompt(context)
        
        # Generate the query using LLM
        cypher_query = self._generate_cypher_with_llm(
            "Generate a comprehensive Cypher query for the entire entity context.",
            prompt_data
        )
        
        # Return the query in the expected format
        return {"cypher_query": cypher_query}
    
    def build_incremental_cypher(self, context, page_data, page_num):
        """
        Generate an incremental Cypher query for a single page's data.
        
        Args:
            context: The full entity context
            page_data: The extracted data from this specific page
            page_num: The page number
            
        Returns:
            A JSON object with a "cypher_query" field for this page's entities.
        """
        # Get primary category from context for normalization
        primary_category = self._get_primary_category(context)
        
        # Create a structured representation of page entities
        prompt_data = {
            "page_number": page_num,
            "primary_category": primary_category,
            "page_data": page_data
        }
        
        # Generate the query using LLM
        cypher_query = self._generate_cypher_with_llm(
            f"Generate an incremental Cypher query for page {page_num}. "
            f"This should only include entities from this specific page.",
            prompt_data
        )
        
        # Return the query with page info
        return {
            "cypher_query": cypher_query,
            "page": page_num
        }
    
    def _format_context_for_prompt(self, context):
        """Format the context data into a cleaner structure for the LLM prompt."""
        # Get primary category
        primary_category = self._get_primary_category(context)
        
        # Format subcategories with their parent info
        subcategories = []
        for subcat_name, subcat_info in context.get("sub_category", {}).items():
            subcategories.append({
                "name": subcat_name,
                "parent_category": subcat_info.get("parent_category", primary_category)
            })
        
        # Format guidelines with their parent info
        guidelines = []
        for guideline_desc, guideline_info in context.get("guideline", {}).items():
            guidelines.append({
                "description": guideline_desc,
                "parent_subcategory": guideline_info.get("parent_subcategory")
            })
        
        # Format pending rules
        pending_rules = []
        for rule_info in context.get("pending_rules", []):
            if "rule" in rule_info:
                rule = rule_info["rule"].copy()
                rule["guideline_hint"] = rule_info.get("guideline_hint")
                rule["subcategory_hint"] = rule_info.get("subcategory_hint")
                pending_rules.append(rule)
        
        # Return formatted data
        return {
            "primary_category": primary_category,
            "subcategories": subcategories,
            "guidelines": guidelines,
            "pending_rules": pending_rules
        }
    
    def _get_primary_category(self, context):
        """Extract the primary category from context."""
        # Find primary category
        for cat_name, cat_info in context.get("offensive_content_category", {}).items():
            if cat_info.get('is_primary'):
                return cat_name
        
        # Default if no primary category found
        if context.get("offensive_content_category"):
            return list(context["offensive_content_category"].keys())[0]
        return "Firearms & Accessories"
    
    def _generate_cypher_with_llm(self, instruction, data):
        """
        Generate a Cypher query using the LLM.
        
        Args:
            instruction: Specific instructions for this query
            data: Structured entity data
            
        Returns:
            Cypher query string
        """
        # Format the user message with the instruction and data
        user_message = f"{instruction}\n\nEntity Data:\n{json.dumps(data, indent=2)}"
        
        # Prepare the API call
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.2  # Lower temperature for more consistent queries
        }
        
        # Call the API with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                # Extract the query from the response
                result = response.json()
                cypher_query = result["choices"][0]["message"]["content"].strip()
                
                # Clean up the response (remove markdown code blocks if present)
                if cypher_query.startswith("```") and cypher_query.endswith("```"):
                    # Extract content between triple backticks
                    lines = cypher_query.split("\n")
                    if len(lines) > 2:
                        # Remove first and last lines (the ```cypher and ```)
                        cypher_query = "\n".join(lines[1:-1])
                
                return cypher_query
                
            except Exception as e:
                print(f"Error during Cypher generation (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # Return a basic query if all retries fail
                    return f"MERGE (occ:Offensive_Content_Category {{name: 'Firearms & Accessories'}})"