#!/usr/bin/env python3
"""
Create test MAY_VIOLATE relationships between products and compliance subcategories.
"""

import os
import sys
from neo4j import GraphDatabase

# Product Types and compliance subcategories with scores
relationships = [
    {
        "product_type": "Swimsuit Sets",
        "subcategory_id": "Accidental_Nudity",
        "confidence_score": 0.85,
        "reasoning": "Swimwear inherently has a high risk of accidental exposure in product imagery, during use, or in customer reviews. The form-fitting nature and minimal coverage of many swimsuit designs significantly increases the potential for unintentional exposure, especially in action shots or when demonstrating the product's fit."
    },
    {
        "product_type": "Lingerie Camisoles",
        "subcategory_id": "Fetish_Content",
        "confidence_score": 0.78,
        "reasoning": "Lingerie camisoles are often marketed with sensual imagery that can cross into fetish territory. The sheer or lace fabrics, marketing context that emphasizes sexuality, and styling that draws attention to intimate areas makes these products high risk for fetish associations, especially when combined with other lingerie pieces."
    },
    {
        "product_type": "Teddies & Bodystockings",
        "subcategory_id": "Entertainment_Nudity",
        "confidence_score": 0.92,
        "reasoning": "Teddies and bodystockings frequently appear in adult entertainment contexts and are closely associated with adult film/entertainment industry. These garments are often extremely revealing or sheer, and product marketing frequently references or suggests entertainment contexts that involve nudity. Their primary purpose is often considered intimate or adult entertainment."
    },
    {
        "product_type": "Body Chains",
        "subcategory_id": "Artistic_Nudity",
        "confidence_score": 0.75,
        "reasoning": "Body chains are frequently depicted in artistic photography that showcases the human form, often with minimal clothing. Marketing these products typically requires artistic nude or semi-nude imagery to demonstrate how the chains lay against the body. The aesthetic presentation often emphasizes artistic body presentation rather than practical function."
    }
]

class Neo4jConnector:
    def __init__(self, uri, username, password, database="neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None

    def connect(self):
        print("Connecting to Neo4j...")
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1")
                list(result)
            print("Connected successfully!")
        except Exception as e:
            print(f"Error connecting to Neo4j: {str(e)}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()
            print("Connection closed")

    def create_product_type_node(self, product_type):
        query = """
        MERGE (pt:ProductType {name: $product_type})
        ON CREATE SET pt.created_at = datetime()
        RETURN pt
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, product_type=product_type)
            return list(result)

    def create_subcategory_node(self, subcategory_id, label=None):
        # If label is not provided, use the ID
        if not label:
            label = subcategory_id.replace("_", " ")
        
        query = """
        MERGE (s:Subcategory {id: $subcategory_id})
        ON CREATE SET s.label = $label, s.created_at = datetime()
        RETURN s
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, subcategory_id=subcategory_id, label=label)
            return list(result)

    def create_may_violate_relationship(self, product_type, subcategory_id, confidence_score, reasoning):
        query = """
        MATCH (pt:ProductType {name: $product_type})
        MATCH (s:Subcategory {id: $subcategory_id})
        MERGE (pt)-[r:MAY_VIOLATE {
            confidence_score: $confidence_score,
            reasoning: $reasoning
        }]->(s)
        RETURN r
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query, 
                product_type=product_type,
                subcategory_id=subcategory_id,
                confidence_score=confidence_score,
                reasoning=reasoning
            )
            return list(result)

def main():
    # Neo4j connection details
    uri = "bolt://localhost:7687"
    username = "neo4j"
    password = "Rathum12!"
    database = "neo4j"
    
    connector = Neo4jConnector(uri, username, password, database)
    
    try:
        connector.connect()
        
        # Create relationships
        for rel in relationships:
            print(f"Creating relationship for {rel['product_type']} -> {rel['subcategory_id']}")
            
            # Create nodes first
            connector.create_product_type_node(rel["product_type"])
            connector.create_subcategory_node(rel["subcategory_id"])
            
            # Create relationship
            connector.create_may_violate_relationship(
                rel["product_type"],
                rel["subcategory_id"],
                rel["confidence_score"],
                rel["reasoning"]
            )
            
        print("All relationships created successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        connector.close()

if __name__ == "__main__":
    main()