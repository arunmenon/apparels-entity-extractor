#!/usr/bin/env python3
"""
Graph-Based Weapons Taxonomy Loader

This script loads a weapons taxonomy represented as a graph with nodes and edges
into a Neo4j database. The taxonomy follows a graph structure with:

1. Node types:
   - Category (root node)
   - Subcategory (weapon types)
   - ComplianceArea (regulatory areas)
   - Law/Regulation (specific laws)

2. Edge types:
   - <parent_of> (connecting Category to Subcategories)
   - <regulated_by> (connecting Subcategories to ComplianceAreas)
   - <governed_by> (connecting ComplianceAreas to Law/Regulations)
"""

import os
import json
import logging
import sys
from neo4j import GraphDatabase

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("weapons_graph_taxonomy_loader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("weapons_graph_taxonomy_loader")

class Neo4jDatabase:
    def __init__(self, uri, username, password, database):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None

    def connect(self):
        logger.info("Connecting to Neo4j...")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        logger.info("Connected successfully!")

    def execute_query(self, query, params=None):
        """Execute a single query with parameters."""
        if params:
            logger.debug(f"Executing query with params: {params}")
        else:
            logger.debug(f"Executing query: {query[:100]}...")
        success = False
        
        with self.driver.session(database=self.database) as session:
            try:
                result = session.run(query, params or {})
                success = True
                logger.debug("Query executed successfully")
            except Exception as e:
                logger.error(f"Error executing query: {str(e)}")
                # Log the failed query to a separate file for review
                with open("failed_query.log", "a") as log_file:
                    log_file.write(f"Failed query:\n{query}\nParams: {params}\nError: {str(e)}\n\n")
        
        return success
    
    def execute_batch(self, queries):
        logger.info(f"Executing batch with {len(queries)} queries...")
        successful_queries = 0
        failed_queries = 0

        # Execute each query in its own transaction to prevent one failure from affecting others
        with self.driver.session(database=self.database) as session:
            for query in queries:
                try:
                    # Execute the query in its own transaction
                    result = session.run(query)
                    # Record the result
                    successful_queries += 1
                except Exception as e:
                    failed_queries += 1
                    # Log the failed query to a separate file for review
                    with open("failed_queries.log", "a") as log_file:
                        log_file.write(f"Failed query:\n{query}\nError: {str(e)}\n\n")
                    
                    # Print detailed error for debugging
                    logger.error(f"Error executing query: {query[:100]}...")
                    logger.error(f"Exception: {e}")
        
        # Summary of batch execution
        logger.info(f"Completed executing batch. Successful queries: {successful_queries}")
        logger.info(f"Failed queries: {failed_queries}")

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed.")

class WeaponsGraphTaxonomyLoader:
    """Class for loading a graph-based weapons taxonomy into Neo4j."""
    
    def __init__(self, uri, username, password, database, taxonomy_file=None):
        """Initialize the taxonomy loader."""
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.taxonomy_file = taxonomy_file or os.path.join(project_root, 'taxonomy', 'weapons_taxonomy_graph_merged.json')
        self.graph_db = Neo4jDatabase(uri, username, password, database)
        self.counts = {
            "CATEGORY_NODES": 0,
            "SUBCATEGORY_NODES": 0,
            "COMPLIANCE_AREA_NODES": 0,
            "LAW_REGULATION_NODES": 0,
            "PARENT_OF_EDGES": 0,
            "REGULATED_BY_EDGES": 0,
            "GOVERNED_BY_EDGES": 0
        }
    
    def connect_to_database(self):
        """Connect to the Neo4j database."""
        self.graph_db.connect()
        
    def close_database(self):
        """Close the database connection."""
        self.graph_db.close()
    
    def create_indexes(self):
        """Create necessary indexes for the taxonomy nodes."""
        logger.info("Creating indexes for weapons taxonomy nodes...")
        
        index_queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Category) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Subcategory) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:ComplianceArea) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Law_Regulation) ON (n.id)"
        ]
        
        self.graph_db.execute_batch(index_queries)
        logger.info("Created indexes for weapons taxonomy")
    
    def load_taxonomy(self):
        """Load the taxonomy from the JSON file and import it into Neo4j."""
        try:
            # Check if the taxonomy file exists
            if not os.path.exists(self.taxonomy_file):
                logger.error(f"Taxonomy file not found: {self.taxonomy_file}")
                return False
            
            # Load the JSON file
            logger.info(f"Loading taxonomy from: {self.taxonomy_file}")
            with open(self.taxonomy_file, 'r') as f:
                taxonomy = json.load(f)
            
            # Connect to the database
            self.connect_to_database()
            
            # Create indexes
            self.create_indexes()
            
            # Process the taxonomy
            self._import_nodes(taxonomy.get("nodes", []))
            self._import_edges(taxonomy.get("edges", []))
            
            # Report summary
            logger.info("Weapons graph taxonomy import completed")
            logger.info(f"Imported {self.counts['CATEGORY_NODES']} category nodes")
            logger.info(f"Imported {self.counts['SUBCATEGORY_NODES']} subcategory nodes")
            logger.info(f"Imported {self.counts['COMPLIANCE_AREA_NODES']} compliance area nodes")
            logger.info(f"Imported {self.counts['LAW_REGULATION_NODES']} law/regulation nodes")
            logger.info(f"Created {self.counts['PARENT_OF_EDGES']} parent-of relationships")
            logger.info(f"Created {self.counts['REGULATED_BY_EDGES']} regulated-by relationships")
            logger.info(f"Created {self.counts['GOVERNED_BY_EDGES']} governed-by relationships")
            
            # Close the connection
            self.close_database()
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading taxonomy: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.close_database()
            return False
    
    def _import_nodes(self, nodes):
        """Import all nodes from the taxonomy."""
        logger.info(f"Importing {len(nodes)} nodes...")
        
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            node_label = node.get("label", "")
            
            if not node_id or not node_type:
                logger.warning(f"Skipping node with missing id or type: {node}")
                continue
            
            # Create appropriate Neo4j node based on type
            if node_type == "Category":
                self._create_category_node(node_id, node_label)
            elif node_type == "Subcategory":
                self._create_subcategory_node(node_id, node_label)
            elif node_type == "ComplianceArea":
                self._create_compliance_area_node(node_id, node_label)
            elif node_type == "Law/Regulation":
                self._create_law_regulation_node(node_id, node_label)
            else:
                logger.warning(f"Unknown node type: {node_type} for node {node_id}")
    
    def _create_category_node(self, node_id, node_label):
        """Create a Category node in Neo4j."""
        logger.info(f"Creating Category node: {node_id}")
        
        query = """
        MERGE (c:Category {id: $id})
        SET c.label = $label
        RETURN c
        """
        
        params = {
            "id": node_id,
            "label": node_label
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["CATEGORY_NODES"] += 1
    
    def _create_subcategory_node(self, node_id, node_label):
        """Create a Subcategory node in Neo4j."""
        logger.info(f"Creating Subcategory node: {node_id}")
        
        query = """
        MERGE (s:Subcategory {id: $id})
        SET s.label = $label
        RETURN s
        """
        
        params = {
            "id": node_id,
            "label": node_label
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["SUBCATEGORY_NODES"] += 1
    
    def _create_compliance_area_node(self, node_id, node_label):
        """Create a ComplianceArea node in Neo4j."""
        logger.info(f"Creating ComplianceArea node: {node_id}")
        
        query = """
        MERGE (ca:ComplianceArea {id: $id})
        SET ca.label = $label
        RETURN ca
        """
        
        params = {
            "id": node_id,
            "label": node_label
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["COMPLIANCE_AREA_NODES"] += 1
    
    def _create_law_regulation_node(self, node_id, node_label):
        """Create a Law_Regulation node in Neo4j."""
        logger.info(f"Creating Law_Regulation node: {node_id}")
        
        # Replace forward slash in type name for Neo4j label
        query = """
        MERGE (l:Law_Regulation {id: $id})
        SET l.label = $label
        RETURN l
        """
        
        params = {
            "id": node_id,
            "label": node_label
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["LAW_REGULATION_NODES"] += 1
    
    def _import_edges(self, edges):
        """Import all edges from the taxonomy."""
        logger.info(f"Importing {len(edges)} edges...")
        
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            relationship = edge.get("relationship", "")
            properties = edge.get("properties", {})
            
            if not source or not target or not relationship:
                logger.warning(f"Skipping edge with missing source, target, or relationship: {edge}")
                continue
            
            # Create appropriate Neo4j relationship based on relationship type
            if relationship == "<parent_of>":
                self._create_parent_of_edge(source, target, properties)
            elif relationship == "<regulated_by>":
                self._create_regulated_by_edge(source, target, properties)
            elif relationship == "<governed_by>":
                self._create_governed_by_edge(source, target, properties)
            else:
                logger.warning(f"Unknown relationship type: {relationship} between {source} and {target}")
    
    def _create_parent_of_edge(self, source, target, properties):
        """Create a PARENT_OF relationship in Neo4j."""
        logger.info(f"Creating PARENT_OF relationship: {source} -> {target}")
        
        description = properties.get("description", "") if properties else ""
        
        # Allow parent_of between any nodes, not just Category to Subcategory
        query = """
        MATCH (s {id: $source})
        MATCH (t:Subcategory {id: $target})
        MERGE (s)-[r:PARENT_OF]->(t)
        """
        
        # Add description property if it exists
        if description:
            query += "SET r.description = $description"
            
        query += """
        RETURN r
        """
        
        params = {
            "source": source,
            "target": target,
            "description": description
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["PARENT_OF_EDGES"] += 1
    
    def _create_regulated_by_edge(self, source, target, properties):
        """Create a REGULATED_BY relationship in Neo4j."""
        logger.info(f"Creating REGULATED_BY relationship: {source} -> {target}")
        
        # Convert the notes list to a JSON string for storage
        notes = json.dumps(properties.get("notes", [])) if properties and "notes" in properties else "[]"
        
        query = """
        MATCH (s:Subcategory {id: $source})
        MATCH (t:ComplianceArea {id: $target})
        MERGE (s)-[r:REGULATED_BY]->(t)
        SET r.notes = $notes
        RETURN r
        """
        
        params = {
            "source": source,
            "target": target,
            "notes": notes
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["REGULATED_BY_EDGES"] += 1
    
    def _create_governed_by_edge(self, source, target, properties):
        """Create a GOVERNED_BY relationship in Neo4j."""
        logger.info(f"Creating GOVERNED_BY relationship: {source} -> {target}")
        
        scope = properties.get("scope", "") if properties else ""
        
        query = """
        MATCH (s:ComplianceArea {id: $source})
        MATCH (t:Law_Regulation {id: $target})
        MERGE (s)-[r:GOVERNED_BY]->(t)
        SET r.scope = $scope
        RETURN r
        """
        
        params = {
            "source": source,
            "target": target,
            "scope": scope
        }
        
        self.graph_db.execute_query(query, params)
        self.counts["GOVERNED_BY_EDGES"] += 1

def main():
    """Main function to run the weapons graph taxonomy loader."""
    # Neo4j connection settings
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "Rathum12!"
    neo4j_database = "neo4j"
    
    import argparse
    parser = argparse.ArgumentParser(description='Load weapons graph taxonomy into Neo4j')
    parser.add_argument('--taxonomy-file', '-f', type=str, help='Path to the weapons taxonomy JSON file')
    args = parser.parse_args()
    
    # Determine the taxonomy file to load
    taxonomy_file = args.taxonomy_file
    if not taxonomy_file:
        project_root = os.path.dirname(os.path.abspath(__file__))
        taxonomy_file = os.path.join(project_root, 'taxonomy', 'weapons_taxonomy_graph.json')
    
    # Create the taxonomy loader
    loader = WeaponsGraphTaxonomyLoader(
        uri=neo4j_uri,
        username=neo4j_user,
        password=neo4j_password,
        database=neo4j_database,
        taxonomy_file=taxonomy_file
    )
    
    # Load the taxonomy
    success = loader.load_taxonomy()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())