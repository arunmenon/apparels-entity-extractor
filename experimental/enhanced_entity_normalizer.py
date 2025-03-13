import os
import json
import re
import difflib
from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase
from collections import defaultdict
import networkx as nx

# Load environment variables
load_dotenv()

class EntityNormalizer:
    """
    Advanced entity normalizer for the Imperium rule heuristics graph
    """
    def __init__(self):
        # Connect to Neo4j
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = "Rathum12"  # Hard-coded for simplicity
        
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Connect to OpenAI
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize entity type taxonomy
        self.initialize_entity_types()
    
    def close(self):
        self.driver.close()
    
    def initialize_entity_types(self):
        """Initialize entity type taxonomy"""
        self.entity_type_taxonomy = {
            "PRODUCT_CATEGORY": [
                "Health & Beauty", "Books & Media", "Electronics", "Apparel", 
                "Home & Garden", "Automotive", "Sports & Outdoors", "Toys & Games",
                "Food & Beverage", "Office Products", "Pet Supplies", "Tools & Home Improvement"
            ],
            "PRODUCT_TYPE": [
                "Device", "Accessory", "Clothing", "Medicine", "Cosmetic", "Tool",
                "Supply", "Equipment", "Software", "Furniture", "Food", "Beverage"
            ],
            "CONTENT_TYPE": [
                "Title", "Description", "Review", "Image", "Video", "Listing"
            ],
            "BRAND": [
                "Brand", "Manufacturer", "Company", "Vendor", "Seller"
            ],
            "ATTRIBUTE": [
                "Color", "Size", "Weight", "Material", "Price", "Condition"
            ]
        }
    
    def _run_query(self, query, params=None):
        """Run a query against Neo4j"""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record for record in result]
    
    def get_all_entities(self):
        """Get all entities from the graph"""
        query = """
        MATCH (entity:Target_Entity)
        OPTIONAL MATCH (entity)<-[:TARGETS]-(rule:Imperium_Rule)
        RETURN entity.name as name, count(rule) as rule_count, collect(rule.rule_id) as rule_ids
        ORDER BY rule_count DESC
        """
        
        result = self._run_query(query)
        return [{
            "name": record["name"],
            "rule_count": record["rule_count"],
            "rule_ids": record["rule_ids"]
        } for record in result]
    
    def get_entity_relationships(self):
        """Get entity co-occurrence relationships"""
        query = """
        MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
        WITH rule, collect(entity.name) as entities
        UNWIND entities as entity1
        UNWIND entities as entity2
        WITH entity1, entity2, count(rule) as weight
        WHERE entity1 < entity2
        RETURN entity1, entity2, weight
        ORDER BY weight DESC
        """
        
        result = self._run_query(query)
        return [{
            "entity1": record["entity1"],
            "entity2": record["entity2"],
            "weight": record["weight"]
        } for record in result]
    
    def find_similar_entities(self, threshold=0.7):
        """Find similar entities using string similarity"""
        entities = self.get_all_entities()
        entity_names = [entity["name"] for entity in entities]
        
        similar_groups = []
        processed = set()
        
        for i, name1 in enumerate(entity_names):
            if name1 in processed:
                continue
            
            group = [name1]
            processed.add(name1)
            
            for j, name2 in enumerate(entity_names):
                if i != j and name2 not in processed:
                    # Calculate string similarity
                    similarity = difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
                    
                    # Word-based similarity
                    words1 = set(name1.lower().split())
                    words2 = set(name2.lower().split())
                    word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2)) if max(len(words1), len(words2)) > 0 else 0
                    
                    # Combined score
                    combined_score = 0.5 * similarity + 0.5 * word_overlap
                    
                    if combined_score >= threshold:
                        group.append(name2)
                        processed.add(name2)
            
            if len(group) > 1:
                similar_groups.append(group)
        
        return similar_groups
    
    def extract_entity_types(self, entity_name):
        """
        Extract entity types using pattern matching and keyword analysis
        """
        entity_lower = entity_name.lower()
        entity_types = []
        
        # Check against taxonomy
        for type_name, keywords in self.entity_type_taxonomy.items():
            for keyword in keywords:
                if keyword.lower() in entity_lower:
                    entity_types.append(type_name)
                    break
        
        # Additional pattern matching
        patterns = [
            (r'product(s)?', 'PRODUCT_TYPE'),
            (r'category|categories', 'PRODUCT_CATEGORY'),
            (r'brand(s)?|manufacturer', 'BRAND'),
            (r'title(s)?|description(s)?|content', 'CONTENT_TYPE'),
            (r'item(s)?|listing(s)?', 'PRODUCT_TYPE')
        ]
        
        for pattern, type_name in patterns:
            if re.search(pattern, entity_lower) and type_name not in entity_types:
                entity_types.append(type_name)
        
        # If no types detected, use AI to suggest
        if not entity_types:
            entity_types = self.ai_suggest_entity_type(entity_name)
        
        return entity_types
    
    def ai_suggest_entity_type(self, entity_name):
        """Use OpenAI to suggest entity types"""
        # Load the prompt template from file
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                   "prompts", "entity_type_detection_prompt.txt")
        
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()
            
        # Format the prompt with the entity name
        prompt = prompt_template.format(entity_name=entity_name)
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Using GPT-4o as requested
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=50
            )
            
            result = response.choices[0].message.content.strip()
            return [category.strip() for category in result.split(',')]
        except Exception as e:
            print(f"Error getting AI suggestion for entity type: {e}")
            return ["OTHER"]
    
    def create_canonical_entities(self, similar_groups):
        """Create canonical entities from similar groups"""
        canonical_entities = {}
        
        for group in similar_groups:
            # Use AI to suggest the best canonical form
            canonical_name = self.ai_suggest_canonical_name(group)
            
            # Map all entities in the group to the canonical form
            for entity in group:
                canonical_entities[entity] = canonical_name
        
        return canonical_entities
    
    def ai_suggest_canonical_name(self, entity_group):
        """Use OpenAI to suggest the best canonical name for a group of similar entities"""
        # Load the prompt template from file
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  "prompts", "entity_normalization_prompt.txt")
        
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()
            
        # Format the prompt with the entity group
        prompt = prompt_template.format(entity_group=json.dumps(entity_group))
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Using GPT-4o as requested
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=50
            )
            
            result = response.choices[0].message.content.strip()
            return result
        except Exception as e:
            print(f"Error getting AI suggestion for canonical name: {e}")
            return entity_group[0]  # Default to first entity in group
    
    def update_graph_with_normalized_entities(self, canonical_entities):
        """Update the graph with normalized entity names"""
        for original, canonical in canonical_entities.items():
            if original != canonical:
                # Create a query to update the entity
                query = """
                MATCH (entity:Target_Entity {name: $original})
                SET entity.original_name = entity.name,
                    entity.name = $canonical,
                    entity.normalized = true
                RETURN entity
                """
                
                try:
                    self._run_query(query, {"original": original, "canonical": canonical})
                    print(f"Updated entity: '{original}' -> '{canonical}'")
                except Exception as e:
                    print(f"Error updating entity '{original}': {e}")
    
    def add_entity_types_to_graph(self):
        """Add entity types to entities in the graph"""
        # Get all entities
        entities = self.get_all_entities()
        
        for entity in entities:
            entity_name = entity["name"]
            entity_types = self.extract_entity_types(entity_name)
            
            if entity_types:
                # Add entity types as a property
                query = """
                MATCH (entity:Target_Entity {name: $name})
                SET entity.entity_types = $types
                RETURN entity
                """
                
                try:
                    self._run_query(query, {"name": entity_name, "types": entity_types})
                    print(f"Added types {entity_types} to entity: '{entity_name}'")
                except Exception as e:
                    print(f"Error adding types to entity '{entity_name}': {e}")
    
    def create_entity_type_nodes(self):
        """Create entity type nodes and relationships"""
        # Get all entities with types
        query = """
        MATCH (entity:Target_Entity)
        WHERE entity.entity_types IS NOT NULL
        RETURN entity.name as name, entity.entity_types as types
        """
        
        result = self._run_query(query)
        
        for record in result:
            entity_name = record["name"]
            entity_types = record["types"]
            
            for entity_type in entity_types:
                # Create entity type node and relationship
                create_query = """
                MERGE (type:Entity_Type {name: $type})
                WITH type
                MATCH (entity:Target_Entity {name: $name})
                MERGE (entity)-[:HAS_TYPE]->(type)
                RETURN type, entity
                """
                
                try:
                    self._run_query(create_query, {"type": entity_type, "name": entity_name})
                    print(f"Created relationship: '{entity_name}' -[:HAS_TYPE]-> '{entity_type}'")
                except Exception as e:
                    print(f"Error creating entity type relationship for '{entity_name}': {e}")
    
    def run_normalization_pipeline(self, similarity_threshold=0.7):
        """Run the complete entity normalization pipeline"""
        print("=" * 80)
        print("ENTITY NORMALIZATION PIPELINE")
        print("=" * 80)
        
        print("\n1. Finding similar entities...")
        similar_groups = self.find_similar_entities(threshold=similarity_threshold)
        
        print(f"\nFound {len(similar_groups)} groups of similar entities:")
        for i, group in enumerate(similar_groups):
            print(f"\nGroup {i+1}:")
            for entity in group:
                print(f"  - {entity}")
        
        if similar_groups:
            print("\n2. Creating canonical entity names...")
            canonical_entities = self.create_canonical_entities(similar_groups)
            
            print("\nCanonical entity mappings:")
            for original, canonical in canonical_entities.items():
                print(f"  - '{original}' -> '{canonical}'")
            
            print("\n3. Updating graph with normalized entities...")
            self.update_graph_with_normalized_entities(canonical_entities)
        else:
            print("\nNo similar entities found to normalize.")
        
        print("\n4. Extracting entity types...")
        self.add_entity_types_to_graph()
        
        print("\n5. Creating entity type nodes and relationships...")
        self.create_entity_type_nodes()
        
        print("\n✅ Entity normalization pipeline completed!")
        
        # Create histogram of entity types
        query = """
        MATCH (type:Entity_Type)<-[:HAS_TYPE]-(entity:Target_Entity)
        RETURN type.name as type, count(entity) as count
        ORDER BY count DESC
        """
        
        result = self._run_query(query)
        
        print("\nEntity Type Distribution:")
        for record in result:
            print(f"  - {record['type']}: {record['count']} entities")
        
        return similar_groups, canonical_entities
    
    def create_visualization(self, output_file="normalized_entity_graph.json"):
        """Create visualization data for the normalized entities and their types"""
        # Get all entities with their types and rules
        query = """
        MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
        OPTIONAL MATCH (entity)-[:HAS_TYPE]->(type:Entity_Type)
        RETURN 
            entity.name as entity_name,
            entity.original_name as original_name,
            collect(DISTINCT type.name) as entity_types,
            collect(DISTINCT rule.rule_id) as rule_ids,
            count(rule) as rule_count
        ORDER BY rule_count DESC
        """
        
        result = self._run_query(query)
        
        # Format for visualization
        entity_data = []
        for record in result:
            entity_data.append({
                "entity_name": record["entity_name"],
                "original_name": record["original_name"],
                "entity_types": record["entity_types"],
                "rule_ids": record["rule_ids"],
                "rule_count": record["rule_count"]
            })
        
        # Get entity relationships (co-occurrences)
        relationships = self.get_entity_relationships()
        
        # Create visualization data
        visualization_data = {
            "entities": entity_data,
            "relationships": relationships
        }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(visualization_data, f, indent=2)
        
        print(f"Visualization data exported to {output_file}")
        return visualization_data
    
def main():
    """Main function for entity normalization"""
    normalizer = EntityNormalizer()
    
    try:
        # Run the normalization pipeline
        normalizer.run_normalization_pipeline()
        
        # Create visualization data
        normalizer.create_visualization()
        
    finally:
        normalizer.close()

if __name__ == "__main__":
    main()