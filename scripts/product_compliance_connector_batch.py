#!/usr/bin/env python3
"""
Product-Compliance Taxonomy Connector (Batch Version)

This script analyzes product types against multiple compliance subcategories in a single API call
to create weighted relationships based on relevance. It uses the OpenAI o1 model to generate 
confidence scores with detailed reasoning for multiple subcategories at once.

The script:
1. Fetches product taxonomy data (PT/PTG) and compliance subcategories from Neo4j
2. Processes products in batches, comparing each against multiple compliance subcategories at once
3. Creates MAY_VIOLATE relationships between products and compliance subcategories
4. Stores confidence scores and reasoning as edge properties
"""

import os
import json
import argparse
import logging
import sys
import time
import re
import random
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Configure logging
def setup_logger(log_file=None, debug=False):
    logger = logging.getLogger("product_compliance_connector")
    
    # Set log level
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

class Neo4jDatabase:
    def __init__(self, uri: str, username: str, password: str, database: str, logger):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        self.logger = logger

    def connect(self) -> None:
        self.logger.info("Connecting to Neo4j...")
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # Verify connection works
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                list(result)
            self.logger.info("Connected successfully!")
        except Exception as e:
            self.logger.error(f"Neo4j connection error: {str(e)}")
            raise

    def execute_query(self, query: str, params: Optional[Dict] = None) -> List:
        if params:
            self.logger.debug(f"Executing query with params: {params}")
        else:
            self.logger.debug(f"Executing query: {query[:100]}...")
        
        with self.driver.session(database=self.database) as session:
            try:
                result = session.run(query, params or {})
                records = list(result)
                self.logger.debug(f"Query returned {len(records)} records")
                return records
            except Exception as e:
                self.logger.error(f"Error executing query: {str(e)}")
                return []
    
    def close(self) -> None:
        if self.driver:
            self.driver.close()
            self.logger.info("Neo4j connection closed")

class ProductComplianceConnector:
    """Connects product taxonomy to compliance taxonomy with weighted relationships using o1"""
    
    def __init__(self, neo4j_db, openai_api_key, logger, subcats_per_batch=5, products_per_batch=1):
        self.db = neo4j_db
        self.logger = logger
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.subcats_per_batch = subcats_per_batch  # Number of subcategories to analyze in one API call
        self.products_per_batch = products_per_batch  # Number of products to process in each batch
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.prompt_template = self._load_prompt_template()
        
    def _load_prompt_template(self):
        """Load prompt template from file"""
        prompt_path = '/Users/arunmenon/projects/apparels-entity-extractor/prompts/product_compliance_batch_prompt.txt'
        try:
            with open(prompt_path, 'r') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error loading prompt template: {str(e)}")
            # Fallback to default prompt
            return """You are an expert compliance analyst. You need to determine if a product type might potentially violate multiple compliance subcategories, and assign a confidence score (0.0 to 1.0) for each.

PRODUCT INFORMATION:
Category: {product_category}
Product Type Group: {product_type_group}
Product Type: {product_type}

ATTRIBUTES:
{attributes_text}

COMPLIANCE SUBCATEGORIES:
{subcategories_text}

TASK:
For EACH subcategory, analyze if this product type could potentially violate or be subject to that compliance subcategory. Consider:
1. The nature of the product and its potential for misuse
2. How the product's attributes might relate to the compliance subcategory
3. Historical precedents of similar products violating this subcategory
4. Regulatory concerns or edge cases that might apply

For each subcategory, determine a confidence score between 0.0 and 1.0:
- 0.0: No relationship or relevance whatsoever
- 0.2: Very unlikely but remotely possible relationship
- 0.4: Possible but uncommon relationship
- 0.6: Moderately likely relationship
- 0.8: Highly likely relationship
- 1.0: Definitively related or high-risk relationship

FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS (a JSON array with one object per subcategory):
[
  {
    "subcategory_id": "<subcategory-id>",
    "confidence_score": <float between 0.0 and 1.0>,
    "reasoning": "<detailed explanation justifying your score>"
  },
  {
    "subcategory_id": "<subcategory-id>",
    "confidence_score": <float between 0.0 and 1.0>,
    "reasoning": "<detailed explanation justifying your score>"
  }
]

Your reasoning for each subcategory must be thorough and directly link the product attributes to that specific compliance subcategory. Pay special attention to the context, examples, and edge cases provided for each subcategory."""
        
    def fetch_product_types(self, category=None, ptg=None) -> List[Dict]:
        """Fetch product types with their attributes and metadata"""
        query = """
        MATCH (cat:ProductCategory)
        MATCH (ptg:ProductTypeGroup)-[:HAS_PT]->(pt:ProductType)
        MATCH (cat)-[:HAS_PTG]->(ptg)
        OPTIONAL MATCH (pt)-[r:HAS_ATTRIBUTE]->(a:Attribute)
        """
        
        # Add filters if specified
        if category:
            query += f" WHERE cat.name = '{category}'"
            if ptg:
                query += f" AND ptg.name = '{ptg}'"
        
        query += """
        RETURN 
            cat.name AS category,
            ptg.name AS product_type_group,
            pt.name AS product_type,
            collect({
                name: a.name,
                type: r.type,
                description: r.description,
                example_values: r.example_values,
                is_variant: r.is_variant_attribute
            }) AS attributes
        """
        
        results = self.db.execute_query(query)
        products = []
        
        for record in results:
            product = {
                'category': record['category'],
                'product_type_group': record['product_type_group'],
                'product_type': record['product_type'],
                'attributes': [attr for attr in record['attributes'] if attr['name']]
            }
            products.append(product)
        
        self.logger.info(f"Fetched {len(products)} product types")
        return products
    
    def fetch_compliance_subcategories(self, compliance_category: str) -> List[Dict]:
        """Fetch compliance subcategories for a given compliance category"""
        query = f"""
        MATCH (cc:Category {{id: '{compliance_category}'}})
        MATCH (cc)-[:PARENT_OF]->(sub:Subcategory)
        RETURN 
            sub.id AS id,
            sub.label AS label,
            sub.description AS description,
            sub.properties AS properties
        """
        
        results = self.db.execute_query(query)
        subcategories = []
        
        for record in results:
            # Parse properties if available (stored as JSON string)
            properties = {}
            if record['properties']:
                if isinstance(record['properties'], str):
                    try:
                        properties = json.loads(record['properties'])
                    except:
                        properties = {}
                else:
                    properties = record['properties']
                    
            subcategory = {
                'id': record['id'],
                'label': record['label'],
                'description': record['description'],
                'properties': properties
            }
            subcategories.append(subcategory)
        
        self.logger.info(f"Fetched {len(subcategories)} compliance subcategories for {compliance_category}")
        return subcategories
    
    def _generate_prompt(self, product: Dict, subcategories: List[Dict]) -> str:
        """Generate prompt for the LLM to analyze a product against multiple compliance subcategories"""
        
        # Format product attributes nicely
        attributes_text = ""
        for attr in product.get('attributes', []):
            attr_desc = attr.get('description', 'No description')
            attr_type = attr.get('type', 'No type')
            attr_examples = attr.get('example_values', '[]')
            
            if isinstance(attr_examples, str):
                try:
                    attr_examples = json.loads(attr_examples)
                except:
                    attr_examples = []
            
            examples_text = ", ".join(str(ex) for ex in attr_examples) if attr_examples else "None provided"
            
            attributes_text += f"""
- {attr['name']}
  Description: {attr_desc}
  Type: {attr_type}
  Examples: {examples_text}
"""
        
        # Format all subcategories
        subcategories_text = ""
        for i, subcategory in enumerate(subcategories):
            # Format subcategory properties
            subcategory_props = ""
            if subcategory.get('properties'):
                props = subcategory['properties']
                if 'context' in props:
                    subcategory_props += f"Context: {props['context']}\n"
                if 'examples' in props:
                    examples = props['examples']
                    subcategory_props += f"Examples: {', '.join(examples)}\n"
                if 'edge_cases' in props:
                    edge_cases = props['edge_cases']
                    subcategory_props += f"Edge Cases: {', '.join(edge_cases)}\n"
                if 'risk_level' in props:
                    subcategory_props += f"Risk Level: {props['risk_level']}\n"
            
            subcategories_text += f"""
SUBCATEGORY {i+1}:
Name: {subcategory['label']}
ID: {subcategory['id']}
Description: {subcategory['description']}
{subcategory_props}
"""
        
        # Fill in template with values - use a safer approach
        try:
            prompt = self.prompt_template.format(
                product_category=product['category'],
                product_type_group=product['product_type_group'],
                product_type=product['product_type'],
                attributes_text=attributes_text,
                subcategories_text=subcategories_text
            )
            self.logger.debug(f"Successfully formatted prompt template for {product['product_type']}")
        except Exception as e:
            self.logger.error(f"Error formatting prompt template: {str(e)}")
            # Fallback to simpler prompt if template formatting fails
            prompt = f"""Analyze if this product might violate compliance subcategories:

PRODUCT: {product['product_type']} (Category: {product['category']}, Group: {product['product_type_group']})
ATTRIBUTES: {attributes_text}

SUBCATEGORIES: 
{subcategories_text}

FORMAT YOUR RESPONSE AS A JSON ARRAY with subcategory_id, confidence_score (0.0-1.0), and reasoning.
"""
        
        return prompt
    
    def analyze_product_compliance_batch(self, product: Dict, subcategories: List[Dict]) -> List[Dict]:
        """Analyze a product against multiple subcategories in a single API call"""
        prompt = self._generate_prompt(product, subcategories)
        
        # Check for dummy mode (to avoid API calls for testing)
        if os.environ.get("DUMMY_MODE", "").lower() == "true":
            self.logger.info("DUMMY_MODE active, returning mock results")
            mock_results = []
            for subcategory in subcategories:
                # Assign varying confidence scores for demonstration
                if product['product_type'] == "Rain Umbrellas" and subcategory['id'] == "Entertainment_Nudity":
                    confidence = 0.3
                    reasoning = "While umbrellas themselves are not associated with nudity, certain artistic or novelty umbrella designs could potentially feature imagery from entertainment sources that contain nudity."
                elif product['product_type'] == "Rain Umbrellas" and subcategory['id'] == "Nudity_in_Mainstream_Film":
                    confidence = 0.3
                    reasoning = "While umbrellas themselves are not associated with nudity, certain artistic or novelty umbrella designs could potentially feature imagery from mainstream films that contain nudity."
                elif product['product_type'] == "Key Cases" and subcategory['id'] == "Adult_Animated_Nudity":
                    confidence = 0.4
                    reasoning = "Key cases could potentially feature decorative designs that include animated or stylized nudity, though this would be uncommon in commercial products."
                else:
                    confidence = 0.0
                    reasoning = f"No relationship between {product['product_type']} and {subcategory['id']}."
                
                mock_results.append({
                    "subcategory_id": subcategory['id'],
                    "confidence_score": confidence,
                    "reasoning": reasoning
                })
            return mock_results
        
        for attempt in range(self.max_retries):
            try:
                # Add a small jitter for thread safety
                if attempt > 0:
                    jitter = random.uniform(0.1, 1.0)
                    time.sleep(jitter)
                
                # Use the responses API format for o1 model
                response = self.openai_client.responses.create(
                    model="o1",
                    input=[
                        {
                            "role": "developer",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    text={
                        "format": {
                            "type": "text"
                        }
                    },
                    reasoning={
                        "effort": "medium"
                    }
                )
                
                # Extract content from response
                # The structure is different than expected - we need to navigate to the actual text content
                if response.output and len(response.output) > 0:
                    for item in response.output:
                        if hasattr(item, 'content') and item.content and len(item.content) > 0:
                            for content_item in item.content:
                                if hasattr(content_item, 'text'):
                                    content = content_item.text
                                    break
                            else:
                                continue
                            break
                    else:
                        content = str(response)
                else:
                    content = str(response)
                
                # Look for JSON array in the response
                try:
                    # Try to parse the entire response as JSON
                    results = json.loads(content)
                    
                    # Validate it's an array
                    if not isinstance(results, list):
                        raise ValueError("Response is not a JSON array")
                    
                    # Validate each item has required fields
                    for result in results:
                        if 'subcategory_id' not in result or 'confidence_score' not in result or 'reasoning' not in result:
                            raise ValueError("Response missing required fields")
                        
                        # Ensure confidence score is in the correct range
                        confidence = float(result['confidence_score'])
                        if not (0 <= confidence <= 1):
                            confidence = max(0, min(1, confidence))
                            result['confidence_score'] = confidence
                    
                    # Map subcategory_ids to ensure they match our input
                    subcategory_ids = {sub['id'] for sub in subcategories}
                    valid_results = []
                    
                    for result in results:
                        if result['subcategory_id'] in subcategory_ids:
                            valid_results.append(result)
                        else:
                            # Try to match the result to a subcategory based on the name
                            for subcategory in subcategories:
                                if subcategory['id'] in result['subcategory_id'] or result['subcategory_id'] in subcategory['id']:
                                    result['subcategory_id'] = subcategory['id']
                                    valid_results.append(result)
                                    break
                    
                    # If we're missing results for some subcategories, add default values
                    found_ids = {result['subcategory_id'] for result in valid_results}
                    for subcategory in subcategories:
                        if subcategory['id'] not in found_ids:
                            valid_results.append({
                                'subcategory_id': subcategory['id'],
                                'confidence_score': 0.0,
                                'reasoning': "No analysis provided by model for this subcategory"
                            })
                    
                    return valid_results
                    
                except json.JSONDecodeError:
                    # If the entire response isn't valid JSON, try to extract JSON using regex
                    json_pattern = r'\[\s*\{[\s\S]*?\}\s*\]'
                    match = re.search(json_pattern, content)
                    
                    if match:
                        try:
                            results = json.loads(match.group(0))
                            
                            # Validate it's an array
                            if not isinstance(results, list):
                                raise ValueError("Extracted JSON is not an array")
                                
                            # Validate each item has required fields
                            for result in results:
                                if 'subcategory_id' not in result or 'confidence_score' not in result or 'reasoning' not in result:
                                    raise ValueError("Extracted JSON missing required fields")
                                
                                # Ensure confidence score is in the correct range
                                confidence = float(result['confidence_score'])
                                if not (0 <= confidence <= 1):
                                    confidence = max(0, min(1, confidence))
                                    result['confidence_score'] = confidence
                                    
                            # Same ID mapping as above
                            subcategory_ids = {sub['id'] for sub in subcategories}
                            valid_results = []
                            
                            for result in results:
                                if result['subcategory_id'] in subcategory_ids:
                                    valid_results.append(result)
                                else:
                                    # Try to match
                                    for subcategory in subcategories:
                                        if subcategory['id'] in result['subcategory_id'] or result['subcategory_id'] in subcategory['id']:
                                            result['subcategory_id'] = subcategory['id']
                                            valid_results.append(result)
                                            break
                            
                            # Add missing subcategories
                            found_ids = {result['subcategory_id'] for result in valid_results}
                            for subcategory in subcategories:
                                if subcategory['id'] not in found_ids:
                                    valid_results.append({
                                        'subcategory_id': subcategory['id'],
                                        'confidence_score': 0.0,
                                        'reasoning': "No analysis provided by model for this subcategory"
                                    })
                            
                            return valid_results
                        except:
                            pass
                    
                    self.logger.warning(f"Failed to parse LLM response as JSON. Attempt {attempt+1}/{self.max_retries}")
                    self.logger.debug(f"Response content: {content}")
                    
                    # If all extraction attempts fail and it's the last retry, return default responses
                    if attempt == self.max_retries - 1:
                        return [
                            {
                                "subcategory_id": sub['id'],
                                "confidence_score": 0.0,
                                "reasoning": "Error parsing LLM response"
                            } for sub in subcategories
                        ]
            except Exception as e:
                error_msg = str(e).lower()
                self.logger.warning(f"LLM API error: {str(e)}. Attempt {attempt+1}/{self.max_retries}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    
                    # Longer delay for rate limit errors
                    if "rate limit" in error_msg or "too many requests" in error_msg or "capacity" in error_msg:
                        delay *= 2
                        self.logger.warning(f"Rate limit detected, increased backoff to {delay:.2f} seconds")
                    
                    self.logger.info(f"Retrying in {delay:.2f} seconds")
                    time.sleep(delay)
                else:
                    return [
                        {
                            "subcategory_id": sub['id'],
                            "confidence_score": 0.0,
                            "reasoning": f"Error calling LLM API: {str(e)}"
                        } for sub in subcategories
                    ]
        
        return [
            {
                "subcategory_id": sub['id'],
                "confidence_score": 0.0,
                "reasoning": "Failed after multiple attempts"
            } for sub in subcategories
        ]
    
    def create_relationship_query(self, product: Dict, subcategory_id: str, analysis: Dict) -> str:
        """Create Cypher query to establish the relationship in the graph"""
        # Escape single quotes in strings
        pt_name = product['product_type'].replace("'", "\\'")
        sub_id = subcategory_id.replace("'", "\\'")
        confidence = analysis['confidence_score']
        reasoning = analysis['reasoning'].replace("'", "\\'")
        
        # Only create relationships if the confidence is above a threshold
        if confidence < 0.2:
            return None
        
        query = f"""
        MATCH (pt:ProductType {{name: '{pt_name}'}})
        MATCH (sub:Subcategory {{id: '{sub_id}'}})
        MERGE (pt)-[r:MAY_VIOLATE {{
            confidence_score: {confidence},
            reasoning: '{reasoning}'
        }}]->(sub)
        RETURN r
        """
        
        return query
    
    def process_subcategory_batch(self, product: Dict, subcat_batch: List[Dict], retry_count=0) -> List[Dict]:
        """Process a single product against a batch of subcategories - thread-safe method"""
        max_retries = 5
        retry_base_delay = 2  # Base delay for exponential backoff in seconds
        
        product_results = []
        
        try:
            self.logger.info(f"Analyzing {product['product_type']} against {len(subcat_batch)} subcategories")
            batch_results = self.analyze_product_compliance_batch(product, subcat_batch)
            
            # Format and add results
            for result in batch_results:
                product_results.append({
                    'product': product,
                    'subcategory_id': result['subcategory_id'],
                    'analysis': {
                        'confidence_score': result['confidence_score'],
                        'reasoning': result['reasoning']
                    }
                })
                
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a rate limit error
            if retry_count < max_retries and ("rate limit" in error_msg or "too many requests" in error_msg or "capacity" in error_msg):
                # Exponential backoff with jitter
                delay = retry_base_delay * (2 ** retry_count) + random.uniform(0, 1)
                self.logger.warning(f"Rate limit hit, retrying in {delay:.2f} seconds (attempt {retry_count+1}/{max_retries})")
                time.sleep(delay)
                # Recursive retry with incremented counter
                return self.process_subcategory_batch(product, subcat_batch, retry_count + 1)
            else:
                self.logger.error(f"Error processing {product['product_type']}: {str(e)}")
                # Return default results for this batch if all retries fail
                for subcategory in subcat_batch:
                    product_results.append({
                        'product': product,
                        'subcategory_id': subcategory['id'],
                        'analysis': {
                            'confidence_score': 0.0,
                            'reasoning': f"Error during analysis: {str(e)}"
                        }
                    })
        
        return product_results
    
    def process_product_batch(self, products: List[Dict], subcategories: List[Dict]) -> List[Dict]:
        """Process a batch of products against batches of subcategories using thread pool"""
        results = []
        all_tasks = []
        
        # Create thread pool
        max_workers = min(10, os.cpu_count() * 2)  # Limit concurrent threads
        self.logger.info(f"Using thread pool with {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # For each product
            for product in products:
                # Split subcategories into batches
                subcategory_batches = [subcategories[i:i+self.subcats_per_batch] 
                                      for i in range(0, len(subcategories), self.subcats_per_batch)]
                
                # Submit each batch as a separate task
                for subcat_batch in subcategory_batches:
                    task = executor.submit(self.process_subcategory_batch, product, subcat_batch)
                    all_tasks.append(task)
            
            # Process results as they complete
            for future in tqdm(as_completed(all_tasks), total=len(all_tasks), desc="Processing batches"):
                try:
                    batch_results = future.result()
                    results.extend(batch_results)
                except Exception as e:
                    self.logger.error(f"Thread error: {str(e)}")
        
        return results
    
    def connect_taxonomies(self, product_category: str = None, ptg: str = None, 
                         compliance_category: str = None, min_confidence: float = 0.2,
                         limit: int = None):
        """Connect product and compliance taxonomies based on analysis"""
        
        # Fetch product types
        products = self.fetch_product_types(product_category, ptg)
        if not products:
            self.logger.error("No products found matching criteria")
            return
        
        # Apply limit if specified (useful for testing)
        if limit and limit > 0:
            self.logger.info(f"Limiting analysis to {limit} products")
            products = products[:limit]
        
        # Fetch compliance subcategories
        if not compliance_category:
            self.logger.error("Compliance category must be specified")
            return
            
        subcategories = self.fetch_compliance_subcategories(compliance_category)
        if not subcategories:
            self.logger.error(f"No subcategories found for compliance category: {compliance_category}")
            return
        
        self.logger.info(f"Processing {len(products)} products against {len(subcategories)} subcategories")
        
        # Process in batches of products
        product_batches = [products[i:i+self.products_per_batch] 
                          for i in range(0, len(products), self.products_per_batch)]
        
        all_results = []
        relationship_queries = []
        
        for i, product_batch in enumerate(tqdm(product_batches)):
            self.logger.info(f"Processing product batch {i+1}/{len(product_batches)}")
            batch_results = self.process_product_batch(product_batch, subcategories)
            all_results.extend(batch_results)
            
            # Create relationship queries
            for result in batch_results:
                query = self.create_relationship_query(
                    result['product'], 
                    result['subcategory_id'], 
                    result['analysis']
                )
                if query and result['analysis']['confidence_score'] >= min_confidence:
                    relationship_queries.append(query)
            
            # Create output directory based on categories
            output_dir = f'product_taxonomy/{product_category}_{compliance_category}'
            os.makedirs(output_dir, exist_ok=True)
            
            # Save intermediate results every 5 batches
            if (i+1) % 5 == 0 or i == len(product_batches) - 1:
                filename = f'{output_dir}/analysis_batch_{i+1}.json'
                self.logger.info(f"Saving intermediate results to {filename}")
                with open(filename, 'w') as f:
                    json.dump(all_results, f, indent=2)
        
        # Execute relationship queries
        self.logger.info(f"Creating {len(relationship_queries)} relationships in Neo4j")
        for query in tqdm(relationship_queries):
            self.db.execute_query(query)
        
        # Save final results to a file in the category directory
        output_dir = f'product_taxonomy/{product_category}_{compliance_category}'
        os.makedirs(output_dir, exist_ok=True)
        
        final_file = f'{output_dir}/complete_analysis.json'
        self.logger.info(f"Saving complete results to {final_file}")
        with open(final_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        # Generate graph structure file
        self.logger.info("Generating graph structure file")
        graph_structure = self._generate_graph_structure(all_results, product_category, compliance_category, min_confidence)
        
        graph_file = f'{output_dir}/graph_structure.json'
        self.logger.info(f"Saving graph structure to {graph_file}")
        with open(graph_file, 'w') as f:
            json.dump(graph_structure, f, indent=2)
        
        self.logger.info("Product-compliance connection complete")
        return all_results
    
    def _generate_graph_structure(self, results: List[Dict], product_category: str, compliance_category: str, min_confidence: float) -> Dict:
        """Generate a graph structure file for offline import to Neo4j"""
        
        # First get unique nodes (products and subcategories)
        product_nodes = {}
        subcategory_nodes = {}
        edges = []
        
        for result in results:
            # Extract product data
            product = result['product']
            product_id = f"{product['product_type']}"
            
            if product_id not in product_nodes:
                product_nodes[product_id] = {
                    "id": product_id,
                    "name": product['product_type'],
                    "type": "ProductType",
                    "properties": {
                        "category": product['category'],
                        "product_type_group": product['product_type_group']
                    }
                }
            
            # Extract subcategory data
            subcategory_id = result['subcategory_id']
            if subcategory_id not in subcategory_nodes:
                # Try to get the label by querying Neo4j
                query = f"""
                MATCH (sub:Subcategory {{id: '{subcategory_id}'}})
                RETURN sub.label, sub.description
                """
                records = self.db.execute_query(query)
                label = subcategory_id
                description = ""
                
                if records and len(records) > 0:
                    label = records[0].get('sub.label', subcategory_id)
                    description = records[0].get('sub.description', "")
                
                subcategory_nodes[subcategory_id] = {
                    "id": subcategory_id,
                    "name": label,
                    "type": "Subcategory",
                    "properties": {
                        "description": description,
                        "parent_category": compliance_category
                    }
                }
            
            # Create edge if confidence score meets threshold
            confidence_score = result['analysis']['confidence_score']
            if confidence_score >= min_confidence:
                edges.append({
                    "source": product_id,
                    "target": subcategory_id,
                    "relationship": "MAY_VIOLATE",
                    "properties": {
                        "confidence_score": confidence_score,
                        "reasoning": result['analysis']['reasoning']
                    }
                })
        
        # Create parent category node
        category_node = {
            "id": compliance_category,
            "name": compliance_category,
            "type": "Category",
            "properties": {}
        }
        
        # Add parent-child relationships for category-subcategory
        for subcategory_id in subcategory_nodes:
            edges.append({
                "source": compliance_category,
                "target": subcategory_id,
                "relationship": "PARENT_OF",
                "properties": {}
            })
        
        # Create parent category for products
        product_category_node = {
            "id": product_category,
            "name": product_category,
            "type": "ProductCategory",
            "properties": {}
        }
        
        # Get ProductTypeGroups
        ptg_nodes = {}
        for product_id, product_node in product_nodes.items():
            ptg = product_node['properties']['product_type_group']
            ptg_id = ptg
            
            if ptg_id not in ptg_nodes:
                ptg_nodes[ptg_id] = {
                    "id": ptg_id,
                    "name": ptg,
                    "type": "ProductTypeGroup",
                    "properties": {
                        "parent_category": product_category
                    }
                }
            
            # Add edge from PTG to PT
            edges.append({
                "source": ptg_id,
                "target": product_id,
                "relationship": "HAS_PT",
                "properties": {}
            })
        
        # Add edges from ProductCategory to PTG
        for ptg_id in ptg_nodes:
            edges.append({
                "source": product_category,
                "target": ptg_id,
                "relationship": "HAS_PTG",
                "properties": {}
            })
        
        # Combine all nodes
        nodes = list(product_nodes.values()) + list(subcategory_nodes.values()) + \
                [category_node] + [product_category_node] + list(ptg_nodes.values())
        
        # Create final structure
        graph_structure = {
            "nodes": nodes,
            "edges": edges
        }
        
        return graph_structure


def main():
    parser = argparse.ArgumentParser(description="Connect product taxonomy to compliance subcategories using o1 (batch version)")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--username", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--database", default="neo4j", help="Neo4j database name")
    parser.add_argument("--log", help="Log file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--product-category", required=True, help="Product category to analyze (e.g., Fashion, Toys)")
    parser.add_argument("--ptg", help="Filter by product type group")
    parser.add_argument("--compliance-category", required=True, help="Compliance category to connect (Nudity or Weapons)")
    parser.add_argument("--min-confidence", type=float, default=0.2, help="Minimum confidence score to create relationship")
    parser.add_argument("--subcats-per-batch", type=int, default=5, help="Number of subcategories to analyze in one API call (default: 5)")
    parser.add_argument("--products-per-batch", type=int, default=1, help="Number of products to process in each batch (default: 1)")
    parser.add_argument("--limit", type=int, help="Limit number of products to process (useful for testing)")
    
    args = parser.parse_args()
    
    # Get OpenAI API key from environment
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Setup logger
    logger = setup_logger(args.log, args.debug)
    
    # Connect to database
    db = Neo4jDatabase(args.uri, args.username, args.password, args.database, logger)
    
    try:
        db.connect()
        
        # Create and run connector
        connector = ProductComplianceConnector(db, openai_api_key, logger, 
                                             args.subcats_per_batch, 
                                             args.products_per_batch)
        connector.connect_taxonomies(
            product_category=args.product_category,
            ptg=args.ptg,
            compliance_category=args.compliance_category,
            min_confidence=args.min_confidence,
            limit=args.limit
        )
        
    except Exception as e:
        logger.error(f"Error during product-compliance connection: {str(e)}")
        sys.exit(1)
    finally:
        db.close()
    
    logger.info("Product-compliance connection completed successfully")


if __name__ == "__main__":
    main()