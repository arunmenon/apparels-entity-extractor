#!/usr/bin/env python3
"""
Product Catalog Taxonomy Loader

This script loads a product taxonomy with attributes into a Neo4j graph database.
It creates a graph structure with:
- Category nodes
- Product Type Group (PTG) nodes
- Product Type (PT) nodes
- Attribute nodes

The attributes are connected to product types with edge properties containing:
- Attribute values
- Attribute metadata (type, description, unit_of_measure, is_variant)
"""

import os
import json
import logging
import sys
import argparse
from typing import Dict, List, Any, Optional, Union
from neo4j import GraphDatabase

# Configure logging
def setup_logger(log_file=None):
    logger = logging.getLogger("catalog_taxonomy_loader")
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
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
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
        
        return success
    
    def execute_batch(self, queries: List[str]) -> None:
        self.logger.info(f"Executing batch with {len(queries)} queries...")
        successful_queries = 0
        failed_queries = 0
        
        # Execute each query in its own transaction
        with self.driver.session(database=self.database) as session:
            for i, query in enumerate(queries):
                try:
                    result = session.run(query)
                    successful_queries += 1
                    if (i+1) % 50 == 0:
                        self.logger.info(f"Progress: {i+1}/{len(queries)} queries completed")
                except Exception as e:
                    failed_queries += 1
                    self.logger.error(f"Query failed: {str(e)}")
                    self.logger.debug(f"Failed query: {query[:100]}...")
        
        # Summary
        self.logger.info(f"Batch complete. Success: {successful_queries}, Failed: {failed_queries}")

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            self.logger.info("Neo4j connection closed")

class CypherQueryBuilder:
    """Builds Cypher queries for catalog taxonomy loading"""
    
    @staticmethod
    def escape_string(value: str) -> str:
        """Escape quotes and backslashes in strings for Cypher queries"""
        if isinstance(value, str):
            return value.replace('\\', '\\\\').replace("'", "\\'")
        return value
    
    @staticmethod
    def property_to_cypher(key: str, value: Any) -> str:
        """Convert a property key-value pair to Cypher syntax"""
        if value is None:
            return f"{key}: null"
        elif isinstance(value, bool):
            return f"{key}: {str(value).lower()}"
        elif isinstance(value, (int, float)):
            return f"{key}: {value}"
        elif isinstance(value, str):
            escaped_value = CypherQueryBuilder.escape_string(value)
            return f"{key}: '{escaped_value}'"
        elif isinstance(value, (dict, list)):
            # Convert complex structures to JSON strings
            json_str = json.dumps(value).replace("'", "\\'")
            return f"{key}: '{json_str}'"
        else:
            # Default fallback for other types
            return f"{key}: '{value}'"
    
    @staticmethod
    def dict_to_cypher_props(props: Dict[str, Any]) -> str:
        """Convert a dictionary of properties to Cypher property syntax"""
        if not props:
            return "{}"
        
        props_list = [CypherQueryBuilder.property_to_cypher(k, v) for k, v in props.items()]
        return "{" + ", ".join(props_list) + "}"
    
    @staticmethod
    def create_category_node(category: str) -> str:
        """Create Cypher query for ProductCategory node"""
        escaped_category = CypherQueryBuilder.escape_string(category)
        return (
            f"MERGE (c:ProductCategory {{name: '{escaped_category}'}}) "
            f"RETURN c"
        )
    
    @staticmethod
    def create_ptg_node(ptg: str, category: str) -> str:
        """Create Cypher query for Product Type Group node and relate to ProductCategory"""
        escaped_ptg = CypherQueryBuilder.escape_string(ptg)
        escaped_category = CypherQueryBuilder.escape_string(category)
        return (
            f"MATCH (c:ProductCategory {{name: '{escaped_category}'}}) "
            f"MERGE (ptg:ProductTypeGroup {{name: '{escaped_ptg}'}}) "
            f"MERGE (c)-[:HAS_PTG]->(ptg) "
            f"RETURN ptg"
        )
    
    @staticmethod
    def create_pt_node(pt: str, ptg: str, category: str) -> str:
        """Create Cypher query for Product Type node and relate to PTG"""
        escaped_pt = CypherQueryBuilder.escape_string(pt)
        escaped_ptg = CypherQueryBuilder.escape_string(ptg)
        escaped_category = CypherQueryBuilder.escape_string(category)
        return (
            f"MATCH (ptg:ProductTypeGroup {{name: '{escaped_ptg}'}}) "
            f"MERGE (pt:ProductType {{name: '{escaped_pt}'}}) "
            f"MERGE (ptg)-[:HAS_PT]->(pt) "
            f"RETURN pt"
        )
    
    @staticmethod
    def create_attribute_node(attr_name: str) -> str:
        """Create Cypher query for Attribute node"""
        escaped_name = CypherQueryBuilder.escape_string(attr_name)
        return (
            f"MERGE (a:Attribute {{name: '{escaped_name}'}}) "
            f"RETURN a"
        )
    
    @staticmethod
    def create_pt_attribute_relationship(
        pt: str, 
        attr_name: str, 
        attr_props: Dict[str, Any]
    ) -> str:
        """Create relationship between Product Type and Attribute with properties"""
        escaped_pt = CypherQueryBuilder.escape_string(pt)
        escaped_attr = CypherQueryBuilder.escape_string(attr_name)
        props_cypher = CypherQueryBuilder.dict_to_cypher_props(attr_props)
        
        return (
            f"MATCH (pt:ProductType {{name: '{escaped_pt}'}}) "
            f"MATCH (a:Attribute {{name: '{escaped_attr}'}}) "
            f"MERGE (pt)-[r:HAS_ATTRIBUTE {props_cypher}]->(a) "
            f"RETURN r"
        )
    
    @staticmethod
    def create_indexes() -> List[str]:
        """Create index queries for faster lookups"""
        return [
            "CREATE INDEX IF NOT EXISTS FOR (c:ProductCategory) ON (c.name)",
            "CREATE INDEX IF NOT EXISTS FOR (ptg:ProductTypeGroup) ON (ptg.name)",
            "CREATE INDEX IF NOT EXISTS FOR (pt:ProductType) ON (pt.name)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Attribute) ON (a.name)"
        ]
    
    @staticmethod
    def clear_database() -> str:
        """Clear the entire database - USE WITH CAUTION"""
        return "MATCH (n) DETACH DELETE n"


class CatalogTaxonomyLoader:
    """Loads catalog taxonomy with attributes into Neo4j"""
    
    def __init__(self, database, logger):
        self.db = database
        self.logger = logger
        self.query_builder = CypherQueryBuilder()
    
    def load_catalog_taxonomy(self, json_file: str, clear_db: bool = False, clear_product_only: bool = False) -> None:
        """Load catalog taxonomy from JSON file into Neo4j"""
        self.logger.info(f"Loading catalog taxonomy from {json_file}")
        
        # Load JSON data
        with open(json_file, 'r') as f:
            catalog_data = json.load(f)
        
        self.logger.info(f"Loaded {len(catalog_data)} product items from JSON")
        
        # Clear database if requested
        if clear_db:
            self.logger.warning("Clearing entire database before loading")
            self.db.execute_query(self.query_builder.clear_database())
        elif clear_product_only:
            self.logger.warning("Clearing only product taxonomy nodes before loading")
            self.db.execute_query("MATCH (c:ProductCategory) DETACH DELETE c")
            self.db.execute_query("MATCH (ptg:ProductTypeGroup) DETACH DELETE ptg")
            self.db.execute_query("MATCH (pt:ProductType) DETACH DELETE pt")
            self.db.execute_query("MATCH (a:Attribute) WHERE NOT (a)--(:ComplianceCategory) DETACH DELETE a")
        
        # Create indexes for performance
        self.logger.info("Creating indexes")
        index_queries = self.query_builder.create_indexes()
        self.db.execute_batch(index_queries)
        
        # Process the data
        self._process_catalog_data(catalog_data)
    
    def _process_catalog_data(self, catalog_data: List[Dict[str, Any]]) -> None:
        """Process catalog data and generate queries"""
        # Track unique entities to avoid duplicate queries
        categories = set()
        ptgs = set()  # (category, ptg) tuples
        pts = set()   # (category, ptg, pt) tuples
        attributes = set()
        
        # Generate queries
        category_queries = []
        ptg_queries = []
        pt_queries = []
        attribute_queries = []
        relationship_queries = []
        
        # Process each product item
        for item in catalog_data:
            category = item.get('category', '')
            ptg = item.get('product_type_group', '')
            pt = item.get('product_type', '')
            attributes_list = item.get('critical_attributes', [])
            
            # Skip invalid entries
            if not category or not ptg or not pt:
                self.logger.warning(f"Skipping invalid entry: {item}")
                continue
            
            # Create Category node if new
            if category not in categories:
                category_queries.append(self.query_builder.create_category_node(category))
                categories.add(category)
            
            # Create PTG node if new
            category_ptg = (category, ptg)
            if category_ptg not in ptgs:
                ptg_queries.append(self.query_builder.create_ptg_node(ptg, category))
                ptgs.add(category_ptg)
            
            # Create PT node if new
            category_ptg_pt = (category, ptg, pt)
            if category_ptg_pt not in pts:
                pt_queries.append(self.query_builder.create_pt_node(pt, ptg, category))
                pts.add(category_ptg_pt)
            
            # Process attributes
            for attr in attributes_list:
                attr_name = attr.get('name', '')
                if not attr_name:
                    continue
                
                # Create Attribute node if new
                if attr_name not in attributes:
                    attribute_queries.append(self.query_builder.create_attribute_node(attr_name))
                    attributes.add(attr_name)
                
                # Prepare attribute properties for the relationship
                attr_props = {
                    'type': attr.get('type', ''),
                    'description': attr.get('description', ''),
                    'example_values': json.dumps(attr.get('example_values', [])),
                    'unit_of_measure': attr.get('unit_of_measure', ''),  # Use empty string for null values
                    'is_variant_attribute': attr.get('is_variant_attribute', False)
                }
                
                # Create relationship between PT and Attribute
                relationship_queries.append(
                    self.query_builder.create_pt_attribute_relationship(
                        pt, attr_name, attr_props
                    )
                )
        
        # Execute queries in appropriate order
        self.logger.info(f"Executing {len(category_queries)} category queries")
        self.db.execute_batch(category_queries)
        
        self.logger.info(f"Executing {len(ptg_queries)} PTG queries")
        self.db.execute_batch(ptg_queries)
        
        self.logger.info(f"Executing {len(pt_queries)} PT queries")
        self.db.execute_batch(pt_queries)
        
        self.logger.info(f"Executing {len(attribute_queries)} attribute queries")
        self.db.execute_batch(attribute_queries)
        
        self.logger.info(f"Executing {len(relationship_queries)} relationship queries")
        self.db.execute_batch(relationship_queries)
        
        self.logger.info("Catalog taxonomy loading complete")


def main():
    parser = argparse.ArgumentParser(description="Load catalog taxonomy with attributes into Neo4j")
    parser.add_argument("--input", required=True, help="Input JSON file with catalog taxonomy")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--username", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--database", default="neo4j", help="Neo4j database name")
    parser.add_argument("--log", help="Log file path")
    parser.add_argument("--clear", action="store_true", help="Clear entire database before loading")
    parser.add_argument("--clear-product", action="store_true", help="Clear only product taxonomy before loading (preserves compliance taxonomy)")
    
    args = parser.parse_args()
    
    # Setup logger
    logger = setup_logger(args.log)
    
    # Connect to database
    db = Neo4jDatabase(args.uri, args.username, args.password, args.database, logger)
    
    try:
        db.connect()
        
        # Create and run loader
        loader = CatalogTaxonomyLoader(db, logger)
        loader.load_catalog_taxonomy(args.input, args.clear, args.clear_product)
        
    except Exception as e:
        logger.error(f"Error during catalog taxonomy loading: {str(e)}")
        sys.exit(1)
    finally:
        db.close()
    
    logger.info("Catalog taxonomy loading completed successfully")


if __name__ == "__main__":
    main()