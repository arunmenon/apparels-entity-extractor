#!/usr/bin/env python3
"""
Generic Taxonomy Loader for Graph Databases

This script provides a flexible framework for loading various taxonomy structures
into a Neo4j graph database. It supports multiple taxonomy types with consistent
graph representation patterns.

Design patterns:
1. Strategy Pattern - Different database strategies
2. Factory Pattern - Database connection creation
3. Singleton Pattern - Logger instance
4. Repository Pattern - Taxonomy data access
5. Builder Pattern - Query construction
"""

import os
import json
import logging
import sys
import argparse
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from neo4j import GraphDatabase as Neo4jDriver

# Configure logging with a singleton pattern
class Logger:
    _instance = None

    def __new__(cls, name=None, log_file=None):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._configure(name or "taxonomy_loader", log_file)
        return cls._instance

    def _configure(self, name, log_file):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create formatters and handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger

# Abstract base class for database interfaces (Strategy Pattern)
class GraphDatabase(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict] = None) -> bool:
        pass
    
    @abstractmethod
    def execute_batch(self, queries: List[str]) -> None:
        pass
    
    @abstractmethod
    def close(self) -> None:
        pass

# Concrete Neo4j implementation
class Neo4jDatabase(GraphDatabase):
    def __init__(self, uri: str, username: str, password: str, database: str):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        self.logger = Logger().get_logger()

    def connect(self) -> None:
        self.logger.info("Connecting to Neo4j...")
        self.driver = Neo4jDriver.driver(self.uri, auth=(self.username, self.password))
        self.logger.info("Connected successfully!")

    def execute_query(self, query: str, params: Optional[Dict] = None) -> bool:
        if params:
            self.logger.debug(f"Executing query with params: {params}")
        else:
            self.logger.debug(f"Executing query: {query[:100]}...")
        success = False
        
        with self.driver.session(database=self.database) as session:
            try:
                result = session.run(query, params or {})
                success = True
                self.logger.debug("Query executed successfully")
            except Exception as e:
                self.logger.error(f"Error executing query: {str(e)}")
                # Log the failed query to a separate file for review
                with open("failed_query.log", "a") as log_file:
                    log_file.write(f"Failed query:\n{query}\nParams: {params}\nError: {str(e)}\n\n")
        
        return success
    
    def execute_batch(self, queries: List[str]) -> None:
        self.logger.info(f"Executing batch with {len(queries)} queries...")
        successful_queries = 0
        failed_queries = 0

        with self.driver.session(database=self.database) as session:
            for query in queries:
                try:
                    # Execute each query in its own transaction
                    result = session.run(query)
                    successful_queries += 1
                except Exception as e:
                    failed_queries += 1
                    # Log the failed query to a separate file for review
                    with open("failed_queries.log", "a") as log_file:
                        log_file.write(f"Failed query:\n{query}\nError: {str(e)}\n\n")
                    
                    # Print detailed error for debugging
                    self.logger.error(f"Error executing query: {query[:100]}...")
                    self.logger.error(f"Exception: {e}")
        
        # Summary of batch execution
        self.logger.info(f"Completed executing batch. Successful queries: {successful_queries}")
        self.logger.info(f"Failed queries: {failed_queries}")

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            self.logger.info("Neo4j connection closed.")

# Factory pattern for creating database connections
class DatabaseFactory:
    @staticmethod
    def create_database(db_type: str, config: Dict[str, Any]) -> GraphDatabase:
        """Factory method to create appropriate database connection."""
        if db_type.lower() == "neo4j":
            return Neo4jDatabase(
                uri=config.get("uri", "bolt://localhost:7687"),
                username=config.get("username", "neo4j"),
                password=config.get("password", ""),
                database=config.get("database", "neo4j")
            )
        # Add support for other database types here
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

# Query builder for Neo4j (Builder pattern)
class CypherQueryBuilder:
    def __init__(self):
        self.query = ""
        self.params = {}
    
    def create_node(self, label: str, id_value: str, properties: Dict[str, Any] = None) -> 'CypherQueryBuilder':
        # Process properties to handle complex objects like dictionaries and lists
        processed_props = {}
        for k, v in (properties or {}).items():
            if isinstance(v, dict) or isinstance(v, list):
                # Convert complex structures to JSON strings for Neo4j storage
                processed_props[k] = json.dumps(v)
            else:
                processed_props[k] = v
        
        # Build the property string for the query
        prop_str = ", ".join([f"{k}: ${k}" for k in processed_props.keys()])
        if prop_str:
            prop_str = f", {prop_str}"
        
        self.query = f"MERGE (n:{label} {{id: $id{prop_str}}}) RETURN n"
        self.params = {"id": id_value, **processed_props}
        return self
    
    def create_relationship(self, source_label: str, source_id: str, 
                         target_label: str, target_id: str,
                         rel_type: str, properties: Dict[str, Any] = None) -> 'CypherQueryBuilder':
        # Build property string for relationship
        prop_str = ""
        if properties and len(properties) > 0:
            prop_list = []
            for k, v in properties.items():
                if isinstance(v, dict) or isinstance(v, list):
                    # Convert complex structures to JSON strings
                    self.params[k] = json.dumps(v)
                else:
                    self.params[k] = v
                prop_list.append(f"r.{k} = ${k}")
            
            if prop_list:
                prop_str = f"SET {', '.join(prop_list)}"
        
        self.query = f"""
        MATCH (src:{source_label} {{id: $source_id}})
        MATCH (tgt:{target_label} {{id: $target_id}})
        MERGE (src)-[r:{rel_type}]->(tgt)
        {prop_str}
        RETURN r
        """
        
        self.params.update({
            "source_id": source_id,
            "target_id": target_id
        })
        
        return self
    
    def build(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "params": self.params
        }

# Domain class to manage taxonomy loading
class TaxonomyLoader:
    """Generic class for loading taxonomy structures into a graph database."""
    
    def __init__(self, db_type: str, db_config: Dict[str, Any], taxonomy_file: str, logger_name: str = None):
        """Initialize the taxonomy loader."""
        self.taxonomy_file = taxonomy_file
        self.graph_db = DatabaseFactory.create_database(db_type, db_config)
        log_file = f"{logger_name or os.path.basename(taxonomy_file).split('.')[0]}_loader.log"
        self.logger = Logger(logger_name or "taxonomy_loader", log_file).get_logger()
        
        # Track statistics on imported items
        self.counts = {}
        self.relationship_map = {
            "<parent_of>": "PARENT_OF",
            "<regulated_by>": "REGULATED_BY",
            "<governed_by>": "GOVERNED_BY", 
            "<regulated_under>": "REGULATED_UNDER",
            "<implements>": "IMPLEMENTS"
        }
        
        # Make sure we can create a flexible counter based on node types
        self.node_type_map = {}
    
    def connect_to_database(self) -> None:
        """Connect to the graph database."""
        self.graph_db.connect()
        
    def close_database(self) -> None:
        """Close the database connection."""
        self.graph_db.close()
    
    def create_indexes(self) -> None:
        """Create necessary indexes for the taxonomy nodes."""
        self.logger.info("Creating indexes for taxonomy nodes...")
        
        # Get unique node types from the taxonomy
        node_types = set()
        try:
            with open(self.taxonomy_file, 'r') as f:
                taxonomy = json.load(f)
                for node in taxonomy.get("nodes", []):
                    node_type = node.get("type", "")
                    # Replace any "/" characters with "_" for Neo4j compatibility
                    node_type = node_type.replace("/", "_")
                    if node_type:
                        node_types.add(node_type)
                        # Add to the node type map for later use
                        self.node_type_map[node.get("type", "")] = node_type
        except Exception as e:
            self.logger.error(f"Error reading taxonomy for indexes: {e}")
            return

        # Create an index for each node type
        index_queries = []
        for node_type in node_types:
            # Create an index on the id field
            index_queries.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{node_type}) ON (n.id)")
        
        self.graph_db.execute_batch(index_queries)
        self.logger.info(f"Created indexes for {len(index_queries)} node types")
    
    def load_taxonomy(self) -> bool:
        """Load the taxonomy from the JSON file and import it into the graph database."""
        try:
            # Check if the taxonomy file exists
            if not os.path.exists(self.taxonomy_file):
                self.logger.error(f"Taxonomy file not found: {self.taxonomy_file}")
                return False
            
            # Load the JSON file
            self.logger.info(f"Loading taxonomy from: {self.taxonomy_file}")
            with open(self.taxonomy_file, 'r') as f:
                taxonomy = json.load(f)
            
            # Connect to the database
            self.connect_to_database()
            
            # Create indexes
            self.create_indexes()
            
            # Initialize counters for all node types and relationship types
            self._initialize_counters(taxonomy)
            
            # Process the taxonomy
            self._import_nodes(taxonomy.get("nodes", []))
            self._import_edges(taxonomy.get("edges", []))
            
            # Report summary
            self.logger.info("Taxonomy import completed")
            for counter_name, count in self.counts.items():
                self.logger.info(f"Imported {count} {counter_name}")
            
            # Close the connection
            self.close_database()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error loading taxonomy: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.close_database()
            return False
    
    def _initialize_counters(self, taxonomy: Dict[str, Any]) -> None:
        """Initialize counters based on the taxonomy structure."""
        # Count node types
        node_types = set()
        for node in taxonomy.get("nodes", []):
            node_type = node.get("type", "")
            if node_type:
                node_types.add(node_type)
                counter_name = f"{node_type.upper()}_NODES"
                self.counts[counter_name] = 0
        
        # Count relationship types
        rel_types = set()
        for edge in taxonomy.get("edges", []):
            rel_type = edge.get("relationship", "")
            if rel_type:
                rel_types.add(rel_type)
                # Convert to database-friendly name
                db_rel_type = self.relationship_map.get(rel_type, rel_type.upper())
                counter_name = f"{db_rel_type}_EDGES"
                self.counts[counter_name] = 0
    
    def _import_nodes(self, nodes: List[Dict[str, Any]]) -> None:
        """Import all nodes from the taxonomy."""
        self.logger.info(f"Importing {len(nodes)} nodes...")
        
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            
            if not node_id or not node_type:
                self.logger.warning(f"Skipping node with missing id or type: {node}")
                continue
            
            # Create appropriate node based on type (using the mapped type for Neo4j compatibility)
            neo4j_type = self.node_type_map.get(node_type, node_type)
            
            # Start with basic properties
            properties = {
                "label": node.get("label", ""),
                "description": node.get("description", ""),
                "type": node.get("type", ""),
                "id": node.get("id", "")
            }
            
            # Include any additional properties from the node
            # This is important for enhanced taxonomies with context, examples, and edge cases
            if "properties" in node:
                properties["properties"] = node["properties"]
            
            # Add any other custom fields that might be in the node
            for key, value in node.items():
                if key not in ["id", "type", "label", "description", "properties"]:
                    properties[key] = value
            
            # Remove empty properties
            properties = {k: v for k, v in properties.items() if v}
            
            # Build and execute the query
            query_builder = CypherQueryBuilder()
            query_data = query_builder.create_node(neo4j_type, node_id, properties).build()
            
            self.graph_db.execute_query(query_data["query"], query_data["params"])
            
            # Update the counter
            counter_name = f"{node_type.upper()}_NODES"
            self.counts[counter_name] = self.counts.get(counter_name, 0) + 1
    
    def _import_edges(self, edges: List[Dict[str, Any]]) -> None:
        """Import all edges from the taxonomy."""
        self.logger.info(f"Importing {len(edges)} edges...")
        
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            relationship = edge.get("relationship", "")
            
            if not source or not target or not relationship:
                self.logger.warning(f"Skipping edge with missing source, target, or relationship: {edge}")
                continue
            
            # Determine node types for source and target
            # This requires knowledge of the taxonomy or additional queries
            # For simplicity, we'll use a generic approach here
            self._create_edge(source, target, relationship, edge.get("properties", {}))
            
            # Update the counter using database-friendly relationship name
            db_rel_type = self.relationship_map.get(relationship, relationship.upper())
            counter_name = f"{db_rel_type}_EDGES"
            self.counts[counter_name] = self.counts.get(counter_name, 0) + 1
    
    def _create_edge(self, source: str, target: str, relationship: str, properties: Dict[str, Any]) -> None:
        """Create a relationship in the graph database with flexible node type detection."""
        # Get the Neo4j relation type name
        db_rel_type = self.relationship_map.get(relationship, relationship.upper())
        
        self.logger.info(f"Creating {db_rel_type} relationship: {source} -> {target}")
        
        # Query to find the source and target node types
        type_query = """
        MATCH (src {id: $source})
        MATCH (tgt {id: $target})
        RETURN labels(src) AS source_labels, labels(tgt) AS target_labels
        """
        
        type_params = {
            "source": source,
            "target": target
        }
        
        # Since we need to know the types, execute a separate query first
        with self.graph_db.driver.session(database=self.graph_db.database) as session:
            try:
                result = session.run(type_query, type_params)
                record = result.single()
                
                if record:
                    source_type = record["source_labels"][0]  # Get the first label
                    target_type = record["target_labels"][0]  # Get the first label
                    
                    # For specific relationships like PARENT_OF, we know the expected types
                    if relationship == "<parent_of>":
                        # PARENT_OF can have flexible source but target should be Subcategory
                        # This helps if source is Category or Subcategory
                        target_type = "Subcategory"
                    elif relationship == "<regulated_by>":
                        # Source is typically a Subcategory, target is ComplianceArea
                        source_type = "Subcategory"
                        target_type = "ComplianceArea"
                    elif relationship == "<governed_by>":
                        # Source is ComplianceArea, target is Law_Regulation
                        source_type = "ComplianceArea"
                        target_type = "Law_Regulation"  # Handle potential slash issues
                    elif relationship == "<regulated_under>":
                        # Source is typically a Subcategory, target is Law_Regulation
                        source_type = "Subcategory"
                        target_type = "Law_Regulation"
                    
                    # Build and execute the relationship query using the discovered types
                    query_builder = CypherQueryBuilder()
                    query_data = query_builder.create_relationship(
                        source_type, source, 
                        target_type, target,
                        db_rel_type, properties
                    ).build()
                    
                    self.graph_db.execute_query(query_data["query"], query_data["params"])
                    
                else:
                    self.logger.warning(f"Could not determine types for {source} -> {target}")
                    # Fallback to generic relationship creation using any nodes that match
                    generic_query = f"""
                    MATCH (src {{id: $source}})
                    MATCH (tgt {{id: $target}})
                    MERGE (src)-[r:{db_rel_type}]->(tgt)
                    RETURN r
                    """
                    self.graph_db.execute_query(generic_query, type_params)
            
            except Exception as e:
                self.logger.error(f"Error creating relationship {source} -> {target}: {e}")

def main():
    """Main function to run the taxonomy loader."""
    parser = argparse.ArgumentParser(description='Load taxonomy into graph database')
    parser.add_argument('--taxonomy-file', '-f', type=str, required=True,
                        help='Path to the taxonomy JSON file')
    parser.add_argument('--db-type', '-d', type=str, default="neo4j",
                        help='Database type (default: neo4j)')
    parser.add_argument('--uri', '-u', type=str, default="bolt://localhost:7687",
                        help='Database URI (default: bolt://localhost:7687)')
    parser.add_argument('--username', '-n', type=str, default="neo4j",
                        help='Database username (default: neo4j)')
    parser.add_argument('--password', '-p', type=str, default="Rathum12!",
                        help='Database password')
    parser.add_argument('--database', '-b', type=str, default="neo4j",
                        help='Database name (default: neo4j)')
    
    args = parser.parse_args()
    
    # Database configuration
    db_config = {
        "uri": args.uri,
        "username": args.username,
        "password": args.password,
        "database": args.database
    }
    
    # Get the taxonomy name from the file for logging
    taxonomy_name = os.path.basename(args.taxonomy_file).split('.')[0]
    
    # Create the taxonomy loader
    loader = TaxonomyLoader(
        db_type=args.db_type,
        db_config=db_config,
        taxonomy_file=args.taxonomy_file,
        logger_name=taxonomy_name
    )
    
    # Load the taxonomy
    success = loader.load_taxonomy()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())