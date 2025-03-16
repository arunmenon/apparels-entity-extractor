#!/usr/bin/env python3
"""
Taxonomy Loader for Enterprise Knowledge Graph

This script imports a detailed compliance taxonomy into the Neo4j graph database,
creating a hierarchical structure of product categories, compliance areas,
regulations, standards, and criteria with their relationships.
"""

import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path
import time

# Add project root to path to allow imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.sys.path.append(project_root)

# Import the graph database connection
from graph_db.graph_strategy_factory import GraphDatabaseFactory

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("taxonomy_loader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("taxonomy_loader")

# Load environment variables
load_dotenv()

class ComplianceTaxonomyLoader:
    """
    Class for loading the compliance taxonomy into Neo4j.
    """
    
    def __init__(self, taxonomy_file=None):
        """
        Initialize the taxonomy loader.
        
        Args:
            taxonomy_file: Path to the JSON taxonomy file (if None, uses default)
        """
        self.taxonomy_file = taxonomy_file or os.path.join(project_root, 'taxonomy', 'compliance_taxonomy.json')
        self.graph_db = None
        self.relationship_counts = {
            "CATEGORIES": 0,
            "COMPLIANCE_AREAS": 0,
            "REGULATIONS": 0,
            "STANDARDS": 0,
            "CRITERIA": 0,
            "RELATIONSHIPS": 0
        }
    
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
    
    def create_indexes(self):
        """Create necessary indexes for the taxonomy nodes."""
        logger.info("Creating indexes for taxonomy nodes...")
        
        index_queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Product_Category) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Compliance_Area) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Regulation) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Standard) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Criterion) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Relation_Type) ON (n.name)"
        ]
        
        self.graph_db.execute_batch(index_queries)
        logger.info("Created indexes for taxonomy")
    
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
            
            # Import the taxonomy
            logger.info("Importing taxonomy structure...")
            self._import_taxonomy(taxonomy)
            
            # Report summary
            logger.info("Taxonomy import completed")
            logger.info(f"Imported {self.relationship_counts['CATEGORIES']} product categories")
            logger.info(f"Imported {self.relationship_counts['COMPLIANCE_AREAS']} compliance areas")
            logger.info(f"Imported {self.relationship_counts['REGULATIONS']} regulations")
            logger.info(f"Imported {self.relationship_counts['STANDARDS']} standards")
            logger.info(f"Imported {self.relationship_counts['CRITERIA']} criteria")
            logger.info(f"Created {self.relationship_counts['RELATIONSHIPS']} inter-area relationships")
            
            # Close the connection
            self.close_database()
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading taxonomy: {e}")
            self.close_database()
            return False
    
    def _import_taxonomy(self, taxonomy):
        """
        Import the taxonomy structure into Neo4j.
        
        Args:
            taxonomy: The loaded taxonomy JSON object
        """
        # Import product categories and their compliance areas
        for category in taxonomy.get("categories", []):
            self._import_product_category(category)
    
    def _import_product_category(self, category):
        """
        Import a product category and its compliance areas.
        
        Args:
            category: A product category object from the taxonomy
        """
        category_name = category.get("name", "")
        if not category_name:
            logger.warning("Skipping category with empty name")
            return
        
        # Create the category node
        logger.info(f"Importing product category: {category_name}")
        cypher = f"""
        MERGE (cat:Product_Category {{name: "{category_name}"}})
        RETURN cat
        """
        self.graph_db.execute_query(cypher)
        self.relationship_counts["CATEGORIES"] += 1
        
        # Import compliance areas for this category
        for compliance_area in category.get("complianceAreas", []):
            self._import_compliance_area(category_name, compliance_area)
    
    def _import_compliance_area(self, category_name, compliance_area):
        """
        Import a compliance area and its components.
        
        Args:
            category_name: The name of the parent product category
            compliance_area: A compliance area object from the taxonomy
        """
        area_name = compliance_area.get("name", "")
        if not area_name:
            logger.warning(f"Skipping compliance area with empty name in category {category_name}")
            return
        
        # Create the compliance area node and link to the category
        logger.info(f"Importing compliance area: {area_name} for category {category_name}")
        cypher = f"""
        MATCH (cat:Product_Category {{name: "{category_name}"}})
        MERGE (area:Compliance_Area {{name: "{area_name}"}})
        MERGE (cat)-[:HAS_COMPLIANCE_AREA]->(area)
        RETURN area
        """
        self.graph_db.execute_query(cypher)
        self.relationship_counts["COMPLIANCE_AREAS"] += 1
        
        # Import regulations for this compliance area
        for regulation in compliance_area.get("regulations", []):
            self._import_regulation(category_name, area_name, regulation)
        
        # Import standards for this compliance area
        for standard in compliance_area.get("standards", []):
            self._import_standard(category_name, area_name, standard)
        
        # Import criteria for this compliance area
        for criterion in compliance_area.get("criteria", []):
            self._import_criterion(category_name, area_name, criterion)
        
        # Import relationships to other compliance areas
        for relationship in compliance_area.get("relationships", []):
            self._import_relationship(category_name, area_name, relationship)
    
    def _import_regulation(self, category_name, area_name, regulation):
        """
        Import a regulation and link it to the compliance area.
        
        Args:
            category_name: The name of the parent product category
            area_name: The name of the parent compliance area
            regulation: A regulation object from the taxonomy
        """
        reg_name = regulation.get("name", "")
        citation = regulation.get("citation", "")
        
        if not reg_name:
            logger.warning(f"Skipping regulation with empty name in area {area_name}")
            return
        
        # Create the regulation node and link to the compliance area
        logger.info(f"Importing regulation: {reg_name}")
        cypher = f"""
        MATCH (area:Compliance_Area {{name: "{area_name}"}})
        MERGE (reg:Regulation {{name: "{reg_name}"}})
        SET reg.citation = "{citation}"
        MERGE (area)-[:HAS_REGULATION]->(reg)
        RETURN reg
        """
        self.graph_db.execute_query(cypher)
        self.relationship_counts["REGULATIONS"] += 1
    
    def _import_standard(self, category_name, area_name, standard):
        """
        Import a standard and link it to the compliance area.
        
        Args:
            category_name: The name of the parent product category
            area_name: The name of the parent compliance area
            standard: A standard object from the taxonomy
        """
        std_name = standard.get("name", "")
        citation = standard.get("citation", "")
        
        if not std_name:
            logger.warning(f"Skipping standard with empty name in area {area_name}")
            return
        
        # Create the standard node and link to the compliance area
        logger.info(f"Importing standard: {std_name}")
        cypher = f"""
        MATCH (area:Compliance_Area {{name: "{area_name}"}})
        MERGE (std:Standard {{name: "{std_name}"}})
        SET std.citation = "{citation}"
        MERGE (area)-[:HAS_STANDARD]->(std)
        RETURN std
        """
        self.graph_db.execute_query(cypher)
        self.relationship_counts["STANDARDS"] += 1
    
    def _import_criterion(self, category_name, area_name, criterion):
        """
        Import a criterion and link it to the compliance area.
        
        Args:
            category_name: The name of the parent product category
            area_name: The name of the parent compliance area
            criterion: A criterion string from the taxonomy
        """
        if not criterion:
            logger.warning(f"Skipping empty criterion in area {area_name}")
            return
        
        # Create the criterion node and link to the compliance area
        criterion = criterion.replace('"', '\\"')  # Escape quotes for Cypher
        logger.info(f"Importing criterion: {criterion[:50]}...")
        cypher = f"""
        MATCH (area:Compliance_Area {{name: "{area_name}"}})
        MERGE (crit:Criterion {{description: "{criterion}"}})
        MERGE (area)-[:HAS_CRITERION]->(crit)
        RETURN crit
        """
        self.graph_db.execute_query(cypher)
        self.relationship_counts["CRITERIA"] += 1
    
    def _import_relationship(self, category_name, source_area_name, relationship):
        """
        Import a relationship between compliance areas.
        
        Args:
            category_name: The name of the parent product category
            source_area_name: The name of the source compliance area
            relationship: A relationship object from the taxonomy
        """
        # Check for the type of relationship
        if "impacts" in relationship:
            rel_type = "IMPACTS"
            target_area_name = relationship["impacts"]
        elif "overlaps" in relationship:
            rel_type = "OVERLAPS_WITH"
            target_area_name = relationship["overlaps"]
        elif "relatedTo" in relationship:
            rel_type = "RELATED_TO"
            target_area_name = relationship["relatedTo"]
        else:
            logger.warning(f"Unknown relationship type in {source_area_name}")
            return
        
        description = relationship.get("description", "").replace('"', '\\"')
        
        # Create the relationship between compliance areas
        logger.info(f"Importing relationship: {source_area_name} {rel_type} {target_area_name}")
        cypher = f"""
        MATCH (source:Compliance_Area {{name: "{source_area_name}"}})
        MATCH (target:Compliance_Area {{name: "{target_area_name}"}})
        MERGE (source)-[r:{rel_type}]->(target)
        SET r.description = "{description}"
        RETURN r
        """
        self.graph_db.execute_query(cypher)
        self.relationship_counts["RELATIONSHIPS"] += 1

def main():
    """Main function to run the taxonomy loader."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Load compliance taxonomy into Neo4j')
    parser.add_argument('--taxonomy-file', '-f', dest='taxonomy_file', type=str,
                        help='Path to the taxonomy JSON file')
    
    args = parser.parse_args()
    
    # Create the taxonomy loader
    loader = ComplianceTaxonomyLoader(taxonomy_file=args.taxonomy_file)
    
    # Load the taxonomy
    success = loader.load_taxonomy()
    
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())