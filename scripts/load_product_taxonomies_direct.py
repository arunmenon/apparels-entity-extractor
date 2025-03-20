#!/usr/bin/env python3
"""
Direct Neo4j loader for product taxonomies.
This script loads both fashion and toys taxonomies directly into Neo4j.
"""

import json
import sys
import os
import logging
from neo4j import GraphDatabase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Neo4jLoader:
    def __init__(self, uri, username, password, database="neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
    
    def connect(self):
        """Connect to Neo4j database"""
        logger.info("Connecting to Neo4j...")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        # Test the connection
        with self.driver.session(database=self.database) as session:
            result = session.run("RETURN 1 as test")
            result.single()  # Will throw an error if connection fails
        logger.info("Connected successfully!")
    
    def close(self):
        """Close the database connection"""
        if self.driver:
            self.driver.close()
            logger.info("Connection closed")
    
    def create_indexes(self):
        """Create indexes for the taxonomy nodes"""
        logger.info("Creating indexes...")
        queries = [
            "CREATE INDEX IF NOT EXISTS FOR (c:ProductCategory) ON (c.name)",
            "CREATE INDEX IF NOT EXISTS FOR (ptg:ProductTypeGroup) ON (ptg.name)",
            "CREATE INDEX IF NOT EXISTS FOR (pt:ProductType) ON (pt.name)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Attribute) ON (a.name)"
        ]
        
        with self.driver.session(database=self.database) as session:
            for query in queries:
                try:
                    session.run(query)
                except Exception as e:
                    logger.error(f"Error creating index: {e}")
        
        logger.info("Indexes created")
    
    def load_category(self, category):
        """Load a product category"""
        query = """
        MERGE (c:ProductCategory {name: $name})
        RETURN c
        """
        
        with self.driver.session(database=self.database) as session:
            session.run(query, name=category)
    
    def load_product_type_group(self, ptg, category):
        """Load a product type group and connect to category"""
        query = """
        MATCH (c:ProductCategory {name: $category})
        MERGE (ptg:ProductTypeGroup {name: $ptg})
        MERGE (c)-[:HAS_PTG]->(ptg)
        RETURN ptg
        """
        
        with self.driver.session(database=self.database) as session:
            session.run(query, category=category, ptg=ptg)
    
    def load_product_type(self, pt, ptg):
        """Load a product type and connect to product type group"""
        query = """
        MATCH (ptg:ProductTypeGroup {name: $ptg})
        MERGE (pt:ProductType {name: $pt})
        MERGE (ptg)-[:HAS_PT]->(pt)
        RETURN pt
        """
        
        with self.driver.session(database=self.database) as session:
            session.run(query, ptg=ptg, pt=pt)
    
    def load_attribute(self, attr_name):
        """Load an attribute"""
        query = """
        MERGE (a:Attribute {name: $name})
        RETURN a
        """
        
        with self.driver.session(database=self.database) as session:
            session.run(query, name=attr_name)
    
    def load_attribute_relationship(self, pt, attr_name, properties):
        """Load relationship between product type and attribute with properties"""
        query = """
        MATCH (pt:ProductType {name: $pt})
        MATCH (a:Attribute {name: $attr})
        MERGE (pt)-[r:HAS_ATTRIBUTE]->(a)
        SET r.type = $type,
            r.description = $description,
            r.example_values = $example_values,
            r.unit_of_measure = $unit,
            r.is_variant_attribute = $is_variant
        RETURN r
        """
        
        with self.driver.session(database=self.database) as session:
            session.run(
                query, 
                pt=pt, 
                attr=attr_name,
                type=properties.get("type", ""),
                description=properties.get("description", ""),
                example_values=json.dumps(properties.get("example_values", [])),
                unit=properties.get("unit_of_measure"),
                is_variant=properties.get("is_variant_attribute", False)
            )
    
    def load_taxonomy_file(self, file_path):
        """Load a complete taxonomy file into Neo4j"""
        logger.info(f"Loading taxonomy from {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loaded {len(data)} products from file")
            
            # Track what we've already processed to avoid duplicates
            categories = set()
            ptgs = set()
            pts = set()
            attributes = set()
            
            # Process by category to be more efficient
            total = len(data)
            for i, item in enumerate(data):
                if i % 10 == 0:
                    logger.info(f"Processing item {i+1}/{total}")
                
                category = item.get("category", "")
                ptg = item.get("product_type_group", "")
                pt = item.get("product_type", "")
                attr_list = item.get("critical_attributes", [])
                
                # Skip invalid entries
                if not category or not ptg or not pt:
                    logger.warning(f"Skipping invalid entry: missing required fields")
                    continue
                
                # Load category if not already loaded
                if category not in categories:
                    self.load_category(category)
                    categories.add(category)
                
                # Load PTG if not already loaded
                if ptg not in ptgs:
                    self.load_product_type_group(ptg, category)
                    ptgs.add(ptg)
                
                # Load PT if not already loaded
                if pt not in pts:
                    self.load_product_type(pt, ptg)
                    pts.add(pt)
                
                # Load attributes and relationships
                for attr in attr_list:
                    attr_name = attr.get("name", "")
                    if not attr_name:
                        continue
                    
                    # Load attribute if not already loaded
                    if attr_name not in attributes:
                        self.load_attribute(attr_name)
                        attributes.add(attr_name)
                    
                    # Load relationship
                    self.load_attribute_relationship(pt, attr_name, attr)
            
            logger.info(f"Successfully loaded taxonomy from {file_path}")
            logger.info(f"Loaded {len(categories)} categories, {len(ptgs)} product type groups, {len(pts)} product types, and {len(attributes)} attributes")
            
        except Exception as e:
            logger.error(f"Error loading taxonomy: {e}")
            raise

def main():
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Load product taxonomies into Neo4j')
    parser.add_argument('--uri', default='bolt://localhost:7687', help='Neo4j URI')
    parser.add_argument('--username', default='neo4j', help='Neo4j username')
    parser.add_argument('--password', required=True, help='Neo4j password')
    parser.add_argument('--fashion-file', default='/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/fashion_augmented_taxonomy.json', 
                        help='Path to fashion taxonomy JSON file')
    parser.add_argument('--toys-file', default='/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/toys_augmented_taxonomy.json',
                        help='Path to toys taxonomy JSON file')
    
    args = parser.parse_args()
    
    # Files to load
    fashion_file = args.fashion_file
    toys_file = args.toys_file
    
    # Initialize loader
    loader = Neo4jLoader(args.uri, args.username, args.password)
    
    try:
        # Connect to Neo4j
        loader.connect()
        
        # Create indexes
        loader.create_indexes()
        
        # Load fashion taxonomy
        logger.info("Loading fashion taxonomy...")
        loader.load_taxonomy_file(fashion_file)
        
        # Load toys taxonomy
        logger.info("Loading toys taxonomy...")
        loader.load_taxonomy_file(toys_file)
        
        logger.info("All taxonomies loaded successfully!")
        
    except Exception as e:
        logger.error(f"Error during loading: {e}")
        sys.exit(1)
    finally:
        loader.close()

if __name__ == "__main__":
    main()