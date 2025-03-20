"""
Enhanced Schema Manager - Module for retrieving and managing graph database schema and context information.

This module provides functions for:
1. Retrieving and caching schema information from Neo4j database
2. Enriching schema with example data from each node and relationship type
3. Formatting rich schema for use in prompts
4. Managing cache TTL and refreshing
"""

import logging
import time
import json
import os
from typing import Dict, List, Any, Optional

from graph_db.graph_strategy_factory import GraphDatabaseFactory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SchemaManager:
    """Enhanced class for managing graph database schema and context information."""
    
    def __init__(self, cache_ttl: int = 3600, cache_dir: str = None, property_metadata_path: str = None):
        """
        Initialize the schema manager.
        
        Args:
            cache_ttl: Time in seconds to cache schema information (default: 1 hour)
            cache_dir: Directory to store persistent cache files (if None, use in-memory only)
            property_metadata_path: Path to the relationship property metadata JSON file
        """
        self.cache_ttl = cache_ttl
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        
        self.schema = None
        self.formatted_schema = None
        self.rich_context = None
        self.formatted_rich_context = None
        self.last_updated = 0
        
        # Property metadata for relationships
        self.property_metadata = {}
        if property_metadata_path and os.path.exists(property_metadata_path):
            try:
                with open(property_metadata_path, 'r') as f:
                    self.property_metadata = json.load(f)
                logging.info(f"Loaded property metadata from {property_metadata_path}")
            except Exception as e:
                logging.warning(f"Error loading property metadata: {e}")
        
        # Try to load from cache if available
        if cache_dir:
            self._load_from_cache()
    
    def _load_from_cache(self):
        """Attempt to load schema and context from disk cache."""
        schema_cache_path = os.path.join(self.cache_dir, 'schema_cache.json') if self.cache_dir else None
        context_cache_path = os.path.join(self.cache_dir, 'context_cache.json') if self.cache_dir else None
        
        if schema_cache_path and os.path.exists(schema_cache_path):
            try:
                with open(schema_cache_path, 'r') as f:
                    cache_data = json.load(f)
                    self.schema = cache_data.get('schema')
                    self.formatted_schema = cache_data.get('formatted_schema')
                    self.last_updated = cache_data.get('timestamp', 0)
                    
                    # Check if cache is still valid
                    if time.time() - self.last_updated <= self.cache_ttl:
                        logger.info("Loaded schema from disk cache")
                    else:
                        logger.info("Schema cache expired, will refresh from database")
                        self.schema = None
                        self.formatted_schema = None
            except Exception as e:
                logger.warning(f"Error loading schema cache: {e}")
        
        if context_cache_path and os.path.exists(context_cache_path):
            try:
                with open(context_cache_path, 'r') as f:
                    cache_data = json.load(f)
                    self.rich_context = cache_data.get('rich_context')
                    self.formatted_rich_context = cache_data.get('formatted_rich_context')
                    
                    # Rich context validation happens when schema is validated
                    if self.schema is None:
                        self.rich_context = None
                        self.formatted_rich_context = None
                        
                logger.info("Loaded rich context from disk cache")
            except Exception as e:
                logger.warning(f"Error loading context cache: {e}")
    
    def _save_to_cache(self):
        """Save current schema and context to disk cache."""
        if not self.cache_dir:
            return
            
        schema_cache_path = os.path.join(self.cache_dir, 'schema_cache.json')
        context_cache_path = os.path.join(self.cache_dir, 'context_cache.json')
        
        # Save schema cache
        try:
            schema_cache = {
                'schema': self.schema,
                'formatted_schema': self.formatted_schema,
                'timestamp': self.last_updated
            }
            with open(schema_cache_path, 'w') as f:
                json.dump(schema_cache, f, indent=2)
                
            logger.info("Saved schema to disk cache")
        except Exception as e:
            logger.warning(f"Error saving schema cache: {e}")
        
        # Save context cache
        if self.rich_context:
            try:
                context_cache = {
                    'rich_context': self.rich_context,
                    'formatted_rich_context': self.formatted_rich_context,
                    'timestamp': self.last_updated
                }
                with open(context_cache_path, 'w') as f:
                    json.dump(context_cache, f, indent=2)
                    
                logger.info("Saved rich context to disk cache")
            except Exception as e:
                logger.warning(f"Error saving context cache: {e}")
    
    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get the current graph schema.
        
        Args:
            force_refresh: Whether to force a refresh of the schema
            
        Returns:
            Dictionary containing schema information
        """
        current_time = time.time()
        
        # Check if schema is stale or needs refresh
        if (force_refresh or 
            self.schema is None or 
            (current_time - self.last_updated) > self.cache_ttl):
            
            logger.info("Retrieving fresh schema from database...")
            self.schema = self._query_schema()
            self.formatted_schema = self.format_schema_for_prompt(self.schema)
            
            # Build rich context with examples
            logger.info("Building rich context with examples...")
            self.rich_context = self._build_rich_context(self.schema)
            self.formatted_rich_context = self.format_rich_context_for_prompt(self.rich_context)
            
            self.last_updated = current_time
            logger.info("Schema and rich context updated successfully")
            
            # Save to disk cache if configured
            self._save_to_cache()
        
        return self.schema
    
    def get_formatted_schema(self, force_refresh: bool = False) -> str:
        """
        Get the schema formatted for prompts.
        
        Args:
            force_refresh: Whether to force a refresh of the schema
            
        Returns:
            Formatted schema string for inclusion in prompts
        """
        # Ensure schema is up to date
        self.get_schema(force_refresh)
        return self.formatted_schema
    
    def get_rich_context(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get the rich context with examples for each node and relationship type.
        
        Args:
            force_refresh: Whether to force a refresh
            
        Returns:
            Dictionary containing rich context information
        """
        # Ensure schema and context are up to date
        self.get_schema(force_refresh)
        return self.rich_context
    
    def get_formatted_rich_context(self, force_refresh: bool = False) -> str:
        """
        Get the rich context formatted for prompts.
        
        Args:
            force_refresh: Whether to force a refresh
            
        Returns:
            Formatted rich context string for inclusion in prompts
        """
        # Ensure schema and context are up to date
        self.get_schema(force_refresh)
        return self.formatted_rich_context
    
    def _query_schema(self) -> Dict[str, Any]:
        """
        Query Neo4j database to retrieve the graph schema.
        
        Returns:
            Dictionary containing schema information
        """
        try:
            # Create and connect to the database
            db = GraphDatabaseFactory.create_graph_database_strategy()
            db.connect()
            
            # Query for node labels and their properties
            node_query = """
            CALL db.schema.nodeTypeProperties() 
            YIELD nodeType, propertyName
            RETURN nodeType AS label, collect(propertyName) AS properties
            """
            node_results = db.execute_query(node_query)
            
            # Query for relationship types and their properties
            rel_query = """
            CALL db.schema.relTypeProperties()
            YIELD relType, propertyName
            RETURN relType AS type, collect(propertyName) AS properties
            """
            rel_results = db.execute_query(rel_query)
            
            # Query for actual relationship connections from schema visualization
            connections_query = """
            CALL db.schema.visualization() 
            YIELD nodes, relationships
            UNWIND relationships AS rel
            RETURN 
                head(nodes) AS source_label,
                rel.type AS relationship,
                last(nodes) AS target_label
            LIMIT 100
            """
            connections_results = db.execute_query(connections_query)
            
            # Query for actual relationship types in the database
            rel_types_query = """
            MATCH ()-[r]->()
            RETURN DISTINCT type(r) AS relationship_type
            """
            rel_types_results = db.execute_query(rel_types_query)
            
            # For each relationship type, get examples of actual connections
            for rel_type_record in rel_types_results:
                rel_type = rel_type_record.get('relationship_type')
                if not rel_type:
                    continue
                    
                # Query to find actual connections with this relationship type
                rel_connections_query = f"""
                MATCH (source)-[r:{rel_type}]->(target)
                WITH DISTINCT labels(source)[0] AS source_label, 
                      '{rel_type}' AS relationship,
                      labels(target)[0] AS target_label,
                      COUNT(*) AS relationship_count
                WHERE relationship_count > 0 AND source_label IS NOT NULL AND target_label IS NOT NULL
                RETURN source_label, relationship, target_label, relationship_count
                LIMIT 5
                """
                try:
                    rel_connections = db.execute_query(rel_connections_query)
                    
                    # Add the relationships to our results
                    for rel in rel_connections:
                        # Create results in the same format as connections_results
                        rel_result = {
                            'source_label': rel.get('source_label'),
                            'relationship': rel.get('relationship'),
                            'target_label': rel.get('target_label')
                        }
                        # Only add if not already in the results
                        exists = False
                        for existing_rel in connections_results:
                            if (existing_rel.get('source_label') == rel_result['source_label'] and
                                existing_rel.get('relationship') == rel_result['relationship'] and
                                existing_rel.get('target_label') == rel_result['target_label']):
                                exists = True
                                break
                        
                        if not exists:
                            connections_results.append(rel_result)
                    
                    logger.debug(f"Added {len(rel_connections)} {rel_type} relationships from instance data")
                except Exception as e:
                    logger.warning(f"Error querying {rel_type} relationships: {e}")
            
            # Format the results
            node_types = {}
            for node in node_results:
                label = node.get('label')
                if label:
                    node_types[label] = node.get('properties', [])
            
            rel_types = {}
            for rel in rel_results:
                type_name = rel.get('type')
                if type_name:
                    rel_types[type_name] = rel.get('properties', [])
            
            # Get relationship patterns
            relationships = []
            relationship_map = {}
            for conn in connections_results:
                source = conn.get('source_label')
                rel = conn.get('relationship')
                target = conn.get('target_label')
                if source and rel and target:
                    rel_pattern = f"({source})-[:{rel}]->({target})"
                    relationships.append(rel_pattern)
                    
                    # Build a map for relationship patterns
                    if source not in relationship_map:
                        relationship_map[source] = {}
                    if rel not in relationship_map[source]:
                        relationship_map[source][rel] = []
                    relationship_map[source][rel].append(target)
            
            # Count node instances
            node_counts = {}
            for node_type in node_types.keys():
                # Remove backticks and colons to ensure valid Cypher
                clean_type = node_type.replace('`', '').replace(':', '')
                count_query = f"MATCH (n:{clean_type}) RETURN count(n) as count"
                try:
                    count_result = db.execute_query(count_query)
                    if count_result and len(count_result) > 0:
                        node_counts[node_type] = count_result[0].get('count', 0)
                except Exception as e:
                    logger.warning(f"Error counting {node_type} nodes: {e}")
                    node_counts[node_type] = 0
            
            # Close the database connection
            db.close()
            
            # Return the complete schema
            return {
                'node_types': node_types,
                'relationship_types': rel_types,
                'relationships': relationships,
                'relationship_map': relationship_map,
                'node_counts': node_counts
            }
        
        except Exception as e:
            logger.error(f"Error retrieving graph schema: {e}")
            return {
                'node_types': {},
                'relationship_types': {},
                'relationships': [],
                'relationship_map': {},
                'node_counts': {},
                'error': str(e)
            }
    
    def _build_rich_context(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build rich context with examples for each node and relationship type.
        
        Args:
            schema: The graph schema information
            
        Returns:
            Dictionary containing rich context information
        """
        rich_context = {
            'node_examples': {},
            'relationship_examples': {},
            'common_queries': []
        }
        
        try:
            # Create and connect to the database
            db = GraphDatabaseFactory.create_graph_database_strategy()
            db.connect()
            
            # Get examples for each node type
            for node_type in schema.get('node_types', {}).keys():
                properties = schema.get('node_types', {}).get(node_type, [])
                if not properties:
                    continue
                    
                # Build a query to get examples
                # Clean node type name for valid Cypher
                clean_type = node_type.replace('`', '').replace(':', '')
                property_string = ", ".join([f"n.{prop} AS {prop}" for prop in properties])
                example_query = f"""
                MATCH (n:{clean_type})
                RETURN {property_string}
                LIMIT 5
                """
                
                try:
                    examples = db.execute_query(example_query)
                    if examples:
                        rich_context['node_examples'][node_type] = examples
                except Exception as e:
                    logger.warning(f"Error getting examples for {node_type}: {e}")
            
            # Get examples for each relationship type
            relationship_map = schema.get('relationship_map', {})
            for source_type, rel_dict in relationship_map.items():
                for rel_type, target_types in rel_dict.items():
                    for target_type in target_types:
                        # Clean type names for valid Cypher
                        clean_source = source_type.replace('`', '').replace(':', '')
                        clean_rel = rel_type.replace('`', '').replace(':', '')
                        clean_target = target_type.replace('`', '').replace(':', '')
                        
                        # Build a query to get relationship examples
                        example_query = f"""
                        MATCH (s:{clean_source})-[r:{clean_rel}]->(t:{clean_target})
                        RETURN s.name AS source_name, t.name AS target_name
                        LIMIT 3
                        """
                        
                        try:
                            examples = db.execute_query(example_query)
                            if examples:
                                rel_key = f"{source_type}-{rel_type}->{target_type}"
                                rich_context['relationship_examples'][rel_key] = examples
                        except Exception as e:
                            # Some of these might fail for various reasons, just log and continue
                            logger.debug(f"Error getting examples for {source_type}-{rel_type}->{target_type}: {e}")
            
            # Generate common queries based on schema
            rich_context['common_queries'] = self._generate_common_queries(schema)
            
            # Find relationships with numeric properties (scores, weights, confidences)
            # and relationships with text properties (explanations, reasonings)
            # This avoids hardcoding any specific relationship type
            
            # Query for relationship types with properties that might include confidence scores
            # Avoid using APOC plugin which might not be available in all environments
            properties_query = """
            MATCH ()-[r]->()
            WHERE ANY(prop IN keys(r) WHERE prop CONTAINS 'score' OR prop CONTAINS 'confidence' 
                  OR prop CONTAINS 'weight' OR prop CONTAINS 'probability')
            RETURN DISTINCT type(r) AS rel_type, 
                   [prop IN keys(r) WHERE prop CONTAINS 'score' OR prop CONTAINS 'confidence' 
                    OR prop CONTAINS 'weight' OR prop CONTAINS 'probability'][0] AS score_property,
                   [prop IN keys(r) WHERE prop CONTAINS 'reason' OR prop CONTAINS 'explanation' 
                    OR prop CONTAINS 'description'][0] AS explanation_property
            """
            
            try:
                # Execute query without relying on APOC
                rel_types_with_properties = db.execute_query(properties_query)
                
                # For each relationship type with numeric properties
                for rel_type_record in rel_types_with_properties:
                    rel_type = rel_type_record.get('rel_type')
                    score_property = rel_type_record.get('score_property')
                    explanation_property = rel_type_record.get('explanation_property')
                    
                    if not rel_type or not score_property:
                        continue
                    
                    # Build query to get examples of this relationship with its properties
                    if explanation_property:
                        examples_query = f"""
                        MATCH (source)-[r:{rel_type}]->(target)
                        WHERE r.{score_property} IS NOT NULL
                        WITH source, r, target, r.{score_property} AS score, r.{explanation_property} AS explanation
                        ORDER BY score DESC
                        LIMIT 5
                        RETURN 
                            labels(source)[0] AS source_type,
                            CASE WHEN source.name IS NOT NULL THEN source.name
                                 WHEN source.id IS NOT NULL THEN source.id
                                 ELSE toString(id(source))
                            END AS source_name,
                            labels(target)[0] AS target_type,
                            CASE WHEN target.name IS NOT NULL THEN target.name
                                 WHEN target.label IS NOT NULL THEN target.label
                                 WHEN target.id IS NOT NULL THEN target.id
                                 ELSE toString(id(target))
                            END AS target_name,
                            "{rel_type}" AS relationship_type,
                            score,
                            explanation
                        """
                    else:
                        examples_query = f"""
                        MATCH (source)-[r:{rel_type}]->(target)
                        WHERE r.{score_property} IS NOT NULL
                        WITH source, r, target, r.{score_property} AS score
                        ORDER BY score DESC
                        LIMIT 5
                        RETURN 
                            labels(source)[0] AS source_type,
                            CASE WHEN source.name IS NOT NULL THEN source.name
                                 WHEN source.id IS NOT NULL THEN source.id
                                 ELSE toString(id(source))
                            END AS source_name,
                            labels(target)[0] AS target_type,
                            CASE WHEN target.name IS NOT NULL THEN target.name
                                 WHEN target.label IS NOT NULL THEN target.label
                                 WHEN target.id IS NOT NULL THEN target.id
                                 ELSE toString(id(target))
                            END AS target_name,
                            "{rel_type}" AS relationship_type,
                            score
                        """
                    
                    try:
                        examples = db.execute_query(examples_query)
                        if examples and len(examples) > 0:
                            # Store examples with relationship type as the key
                            rich_context[f'scored_relationships_{rel_type}'] = examples
                            logger.info(f"Added {len(examples)} {rel_type} relationship examples with scores")
                            
                            # Get top example for query generation
                            top_example = examples[0]
                            source_type = top_example.get('source_type')
                            target_type = top_example.get('target_type')
                            top_score = top_example.get('score', 0)
                            threshold = max(0.7, top_score * 0.8)  # 80% of top score or 0.7, whichever is higher
                            
                            # Add query for this relationship type with high scores
                            rich_context['common_queries'].append({
                                'description': f"Find {source_type}s with high {rel_type} scores (>= {threshold:.1f}) to {target_type}s",
                                'cypher': f"MATCH (source:{source_type})-[r:{rel_type}]->(target:{target_type}) WHERE r.{score_property} >= {threshold} RETURN source.name AS Source, target.name AS Target, r.{score_property} AS Score ORDER BY r.{score_property} DESC"
                            })
                            
                            # If we can detect a hierarchical path, add that query too
                            # Look for relationship paths in the schema
                            for rel_pattern in schema.get('relationships', []):
                                if rel_type in rel_pattern and source_type in rel_pattern and target_type in rel_pattern:
                                    # This relationship is part of this pattern, add a query for it
                                    rich_context['common_queries'].append({
                                        'description': f"Find paths involving {rel_type} with high scores",
                                        'cypher': f"MATCH path = (a)-[*..4]->(source:{source_type})-[r:{rel_type}]->(target:{target_type}) WHERE r.{score_property} >= {threshold} RETURN [node in nodes(path) | CASE WHEN node.name IS NOT NULL THEN node.name ELSE labels(node)[0] END] AS Path, r.{score_property} AS Score LIMIT 10"
                                    })
                                    break
                    except Exception as e:
                        logger.warning(f"Error getting {rel_type} examples: {e}")
                        
            except Exception as e:
                logger.warning(f"Error identifying relationships with scores: {e}")
            
            # Close the database connection
            db.close()
            
        except Exception as e:
            logger.error(f"Error building rich context: {e}")
        
        return rich_context
    
    def _generate_common_queries(self, schema: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generate common queries based on the schema.
        
        Args:
            schema: The graph schema information
            
        Returns:
            List of common queries with descriptions and Cypher
        """
        common_queries = []
        
        # Get all node types
        node_types = list(schema.get('node_types', {}).keys())
        
        # For each node type, add a query to list all instances
        for node_type in node_types:
            # Only add if there are some instances (avoid empty queries)
            count = schema.get('node_counts', {}).get(node_type, 0)
            if count > 0:
                common_queries.append({
                    'description': f"List all {node_type} nodes",
                    'cypher': f"MATCH (n:{node_type}) RETURN n.id, n.name, n.label LIMIT 10"
                })
        
        # For each relationship in the schema, add a query to show connections
        for relationship in schema.get('relationships', [])[:5]:  # Limit to first 5 to avoid too many
            # Basic pattern extraction (not perfect but works for the format we're using)
            parts = relationship.replace('(', '').replace(')', '').split('-[')
            if len(parts) == 2:
                source = parts[0].strip()
                rel_target = parts[1].split(']')
                if len(rel_target) == 2:
                    rel = rel_target[0].replace(':', '')
                    target = rel_target[1].replace('->', '').strip()
                    
                    common_queries.append({
                        'description': f"Show {source} to {target} relationships via {rel}",
                        'cypher': f"MATCH (s:{source})-[r:{rel}]->(t:{target}) RETURN s.name, t.name, type(r) LIMIT 5"
                    })
        
        return common_queries
    
    def format_schema_for_prompt(self, schema: Dict[str, Any]) -> str:
        """
        Format the graph schema into a string suitable for inclusion in a prompt.
        
        Args:
            schema: The graph schema information
            
        Returns:
            Formatted string describing the schema
        """
        formatted = ["TAXONOMY SCHEMA:"]
        
        # Format node types and their properties
        formatted.append("Node Types:")
        for label, properties in schema.get('node_types', {}).items():
            count = schema.get('node_counts', {}).get(label, 0)
            formatted.append(f"- {label} (Count: {count})")
            if properties:
                formatted.append(f"  - Properties: {', '.join(properties)}")
        
        # Format relationship types and their properties
        formatted.append("\nRelationship Types:")
        for rel_type, properties in schema.get('relationship_types', {}).items():
            formatted.append(f"- {rel_type}")
            if properties:
                # Get property metadata if available
                property_details = []
                for prop in properties:
                    prop_metadata = self.property_metadata.get(rel_type, {}).get(prop, {})
                    prop_type = prop_metadata.get('type', 'unknown')
                    semantic_role = prop_metadata.get('semantic_role', 'attribute')
                    
                    # For numeric properties with statistics, add thresholds
                    if prop_type in ('numeric', 'integer') and 'statistics' in prop_metadata:
                        stats = prop_metadata['statistics']
                        high_threshold = stats.get('high_threshold')
                        if high_threshold is not None:
                            property_details.append(
                                f"{prop} ({semantic_role}, {prop_type}, high threshold: {high_threshold})"
                            )
                        else:
                            property_details.append(f"{prop} ({semantic_role}, {prop_type})")
                    else:
                        property_details.append(f"{prop} ({semantic_role}, {prop_type})")
                
                if property_details:
                    formatted.append(f"  - Properties: {', '.join(property_details)}")
                else:
                    formatted.append(f"  - Properties: {', '.join(properties)}")
        
        # Format relationship patterns
        formatted.append("\nRelationship Patterns:")
        for rel in schema.get('relationships', []):
            formatted.append(f"- {rel}")
        
        # Add section for relationships with confidence measures
        confidence_rels = []
        for rel_type, props in self.property_metadata.items():
            for prop, metadata in props.items():
                if metadata.get('semantic_role') == 'confidence_measure':
                    connections = metadata.get('connections', [])
                    stats = metadata.get('statistics', {})
                    if connections and stats:
                        high_threshold = stats.get('high_threshold', 0.7)
                        for conn in connections:
                            source = conn.get('source')
                            target = conn.get('target')
                            if source and target:
                                confidence_rels.append({
                                    "relationship": rel_type,
                                    "property": prop,
                                    "source": source,
                                    "target": target,
                                    "high_threshold": high_threshold
                                })
        
        if confidence_rels:
            formatted.append("\nRelationships with Confidence Measures:")
            for rel in confidence_rels:
                formatted.append(
                    f"- ({rel['source']})-[:{rel['relationship']}]->({rel['target']}) with {rel['property']} >= {rel['high_threshold']}"
                )
        
        return "\n".join(formatted)
    
    def format_rich_context_for_prompt(self, rich_context: Dict[str, Any]) -> str:
        """
        Format the rich context into a string suitable for inclusion in a prompt.
        
        Args:
            rich_context: The rich context information
            
        Returns:
            Formatted string with example data from the database
        """
        if not rich_context:
            return "No rich context available."
            
        formatted = ["GRAPH DATABASE EXAMPLES:"]
        
        # Format node examples
        formatted.append("\nNode Examples:")
        for node_type, examples in rich_context.get('node_examples', {}).items():
            formatted.append(f"\n{node_type} Examples:")
            
            # Format each example
            for i, example in enumerate(examples[:3], 1):  # Limit to 3 examples
                example_str = ", ".join([f"{k}: {v}" for k, v in example.items() if v is not None])
                formatted.append(f"  {i}. {example_str}")
        
        # Format relationship examples
        formatted.append("\nRelationship Examples:")
        for rel_key, examples in rich_context.get('relationship_examples', {}).items():
            formatted.append(f"\n{rel_key} Examples:")
            
            # Format each example
            for i, example in enumerate(examples[:2], 1):  # Limit to 2 examples
                source = example.get('source_name', 'unknown')
                target = example.get('target_name', 'unknown')
                formatted.append(f"  {i}. {source} → {target}")
        
        # Add property metadata examples for important properties
        if self.property_metadata:
            formatted.append("\nRelationship Property Information:")
            for rel_type, properties in self.property_metadata.items():
                for prop_name, metadata in properties.items():
                    # Focus on confidence measures and other important properties
                    semantic_role = metadata.get('semantic_role')
                    if semantic_role in ['confidence_measure', 'explanation']:
                        connections = metadata.get('connections', [])
                        if connections:
                            conn_str = ", ".join([f"({c.get('source')})->({c.get('target')})" for c in connections])
                            formatted.append(f"\n{rel_type}.{prop_name}:")
                            formatted.append(f"  - Type: {metadata.get('type')}")
                            formatted.append(f"  - Role: {semantic_role}")
                            formatted.append(f"  - Used in: {conn_str}")
                            
                            # Add statistics for numeric properties
                            stats = metadata.get('statistics', {})
                            if stats:
                                min_val = stats.get('min')
                                max_val = stats.get('max')
                                high_threshold = stats.get('high_threshold')
                                
                                if min_val is not None and max_val is not None:
                                    formatted.append(f"  - Range: {min_val} to {max_val}")
                                if high_threshold is not None:
                                    formatted.append(f"  - High threshold: >= {high_threshold}")
                            
                            # Add sample values
                            samples = metadata.get('sample_values', [])
                            if samples:
                                sample_str = '; '.join([str(s) for s in samples[:3]])
                                formatted.append(f"  - Sample values: {sample_str}")
        
        # Format common queries
        formatted.append("\nCommon Queries:")
        for i, query in enumerate(rich_context.get('common_queries', []), 1):
            description = query.get('description', 'Unknown query')
            cypher = query.get('cypher', '')
            formatted.append(f"\n{i}. {description}")
            formatted.append(f"   Cypher: {cypher}")
        
        # Add example queries for relationships with confidence scores
        confidence_examples = []
        for rel_type, props in self.property_metadata.items():
            for prop, metadata in props.items():
                if metadata.get('semantic_role') == 'confidence_measure':
                    connections = metadata.get('connections', [])
                    stats = metadata.get('statistics', {})
                    if connections and stats:
                        high_threshold = stats.get('high_threshold', 0.7)
                        for conn in connections:
                            source = conn.get('source')
                            target = conn.get('target')
                            if source and target:
                                confidence_examples.append({
                                    "description": f"Find {source} nodes with high {rel_type} confidence (>= {high_threshold}) to {target} nodes",
                                    "cypher": f"MATCH (s:{source})-[r:{rel_type}]->(t:{target}) WHERE r.{prop} >= {high_threshold} RETURN s.name AS Source, t.name AS Target, r.{prop} AS Confidence ORDER BY r.{prop} DESC LIMIT 10"
                                })
                                
                                # Add example for hierarchical path query if this is MAY_VIOLATE or similar
                                if rel_type in ['MAY_VIOLATE', 'IS_RELATED_TO', 'IS_ASSOCIATED_WITH']:
                                    confidence_examples.append({
                                        "description": f"Find hierarchical paths through {source} nodes with high {rel_type} confidence",
                                        "cypher": f"MATCH path = (parent)-[:PARENT_OF*]->(child)-[r:{rel_type}]->(t:{target}) WHERE r.{prop} >= {high_threshold} RETURN [node IN nodes(path) | coalesce(node.name, labels(node)[0])] AS Hierarchy, t.name AS Target, r.{prop} AS Confidence LIMIT 10"
                                    })
        
        if confidence_examples:
            formatted.append("\nConfidence-Based Query Examples:")
            for i, example in enumerate(confidence_examples, len(rich_context.get('common_queries', [])) + 1):
                formatted.append(f"\n{i}. {example.get('description')}")
                formatted.append(f"   Cypher: {example.get('cypher')}")
        
        # Format scored relationship examples dynamically
        for key, examples in rich_context.items():
            if key.startswith('scored_relationships_') and examples:
                rel_type = key.replace('scored_relationships_', '')
                formatted.append(f"\n{rel_type} Relationship Examples (with scores):")
                
                for i, example in enumerate(examples, 1):
                    source_type = example.get('source_type', 'unknown')
                    source_name = example.get('source_name', 'unknown')
                    target_type = example.get('target_type', 'unknown')
                    target_name = example.get('target_name', 'unknown')
                    score = example.get('score', 0.0)
                    
                    formatted.append(f"\n{i}. {source_type} '{source_name}' → {target_type} '{target_name}'")
                    formatted.append(f"   Score: {score:.2f}")
                    
                    # Include explanation/reasoning if available
                    explanation = example.get('explanation', '')
                    if explanation and len(explanation) > 100:
                        formatted.append(f"   Explanation: {explanation[:100]}...")
                    elif explanation:
                        formatted.append(f"   Explanation: {explanation}")
        
        return "\n".join(formatted)

# Create a singleton instance for global use with persistent caching
cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')

# Default path for property metadata 
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
property_metadata_path = os.path.join(base_dir, 'relationship_property_metadata.json')

schema_manager = SchemaManager(
    cache_ttl=3600, 
    cache_dir=cache_dir,
    property_metadata_path=property_metadata_path if os.path.exists(property_metadata_path) else None
)