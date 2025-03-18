#!/usr/bin/env python3
"""
Generic Taxonomy Verification Tool

This script runs Cypher queries to verify the structure and relationships 
in any taxonomy graph loaded into Neo4j. It provides a flexible approach
to explore and validate taxonomies of different domains.
"""

import os
import sys
import json
import argparse
from neo4j import GraphDatabase

class TaxonomyVerifier:
    """Class to verify taxonomy structure in Neo4j."""

    def __init__(self, uri, username, password, database):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
    
    def connect(self):
        """Connect to Neo4j database."""
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        print("Connected to Neo4j database.")
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
    
    def run_query(self, query, params=None):
        """Run a query against the Neo4j database and return results."""
        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    
    def print_section(self, title):
        """Print a section header."""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    
    def print_json(self, data):
        """Print data as formatted JSON."""
        print(json.dumps(data, indent=2))
    
    def analyze_taxonomy_structure(self, root_node=None):
        """Analyze the overall taxonomy structure."""
        self.print_section("Taxonomy Structure Analysis")
        
        # 1. Count nodes by type
        self.print_section("1. Node Counts by Type")
        query = """
        MATCH (n)
        RETURN labels(n) AS node_type, count(*) AS count
        ORDER BY count DESC
        """
        result = self.run_query(query)
        self.print_json(result)
        
        # 2. Count relationships by type
        self.print_section("2. Relationship Counts by Type")
        query = """
        MATCH ()-[r]->()
        RETURN type(r) AS relationship_type, count(*) AS count
        ORDER BY count DESC
        """
        result = self.run_query(query)
        self.print_json(result)
        
        # 3. Find root node(s) if not specified
        if not root_node:
            self.print_section("3. Identifying Root Node(s)")
            query = """
            MATCH (n:Category)
            WHERE NOT ()-[:PARENT_OF]->(n)
            RETURN n.id AS root_node, n.label AS label
            """
            result = self.run_query(query)
            self.print_json(result)
            
            # Use the first root node found, if any
            if result:
                root_node = result[0]['root_node']
                print(f"Using root node: {root_node}")
        
        if root_node:
            # 4. List all top-level subcategories
            self.print_section(f"4. Top-Level Categories under {root_node}")
            query = """
            MATCH (c:Category {id: $root})-[:PARENT_OF]->(s)
            RETURN s.id AS category, s.label AS description
            ORDER BY category
            """
            result = self.run_query(query, {"root": root_node})
            self.print_json(result)
            
            # 5. Show hierarchy (tree view)
            self.print_section("5. Hierarchical Structure")
            query = """
            MATCH path = (:Category {id: $root})-[:PARENT_OF*1..10]->(child)
            WITH child, length(path) AS depth
            MATCH (parent)-[:PARENT_OF]->(child)
            RETURN 
              CASE 
                WHEN depth = 1 THEN child.id
                WHEN depth = 2 THEN "  ├── " + child.id
                WHEN depth = 3 THEN "  │   ├── " + child.id
                WHEN depth = 4 THEN "  │   │   ├── " + child.id
                WHEN depth = 5 THEN "  │   │   │   ├── " + child.id
                ELSE "  │   │   │   │   ├── " + child.id
              END AS hierarchy,
              child.label AS description,
              depth,
              parent.id AS parent
            ORDER BY depth, child.id
            """
            result = self.run_query(query, {"root": root_node})
            self.print_json(result)
    
    def analyze_regulatory_structure(self):
        """Analyze the regulatory aspects of the taxonomy."""
        # Find compliance areas
        query = """
        MATCH (ca)
        WHERE any(label IN labels(ca) WHERE label = 'ComplianceArea')
        RETURN ca.id AS compliance_area, ca.label AS label
        """
        compliance_areas = self.run_query(query)
        
        if compliance_areas:
            self.print_section("Regulatory Analysis")
            
            # 1. Show compliance areas
            self.print_section("1. Compliance Areas")
            self.print_json(compliance_areas)
            
            # 2. For each compliance area, show what it regulates
            self.print_section("2. Categories Regulated by Compliance Areas")
            for area in compliance_areas:
                area_id = area['compliance_area']
                query = """
                MATCH (s)-[r:REGULATED_BY]->(ca {id: $area_id})
                RETURN s.id AS regulated_category, 
                       s.label AS category_description,
                       r.notes AS regulation_details
                ORDER BY regulated_category
                """
                regulated = self.run_query(query, {"area_id": area_id})
                print(f"\nCompliance Area: {area_id}")
                self.print_json(regulated)
            
            # 3. Check for laws/regulations
            self.print_section("3. Governing Laws and Regulations")
            query = """
            MATCH (l)
            WHERE any(label IN labels(l) WHERE label CONTAINS 'Law' OR label CONTAINS 'Regulation')
            RETURN l.id AS law_regulation, l.label AS full_name
            """
            laws = self.run_query(query)
            if laws:
                self.print_json(laws)
                
                # 4. Show compliance areas governed by specific laws
                self.print_section("4. Compliance Areas Governed by Laws")
                for law in laws:
                    law_id = law['law_regulation']
                    query = """
                    MATCH (ca)-[r]->(l {id: $law_id})
                    WHERE type(r) IN ['GOVERNED_BY', 'REGULATED_UNDER', 'IMPLEMENTS']
                    RETURN ca.id AS compliance_area, 
                           type(r) AS relationship,
                           r.scope AS scope
                    """
                    governed = self.run_query(query, {"law_id": law_id})
                    print(f"\nLaw/Regulation: {law_id}")
                    self.print_json(governed)
                
                # 5. Show complete regulatory paths
                self.print_section("5. Complete Regulatory Paths")
                query = """
                MATCH path = (s)-[:REGULATED_BY|REGULATED_UNDER]->(ca)-[:GOVERNED_BY|IMPLEMENTS]->(l)
                WHERE any(label IN labels(s) WHERE label = 'Subcategory')
                  AND any(label IN labels(ca) WHERE label = 'ComplianceArea')
                  AND any(label IN labels(l) WHERE label CONTAINS 'Law' OR label CONTAINS 'Regulation')
                RETURN s.id AS subcategory, ca.id AS compliance_area, l.id AS law
                LIMIT 25
                """
                paths = self.run_query(query)
                self.print_json(paths)
    
    def check_taxonomy_integrity(self):
        """Perform integrity checks on the taxonomy."""
        self.print_section("Taxonomy Integrity Checks")
        
        # 1. Check for orphan nodes (no incoming or outgoing relationships)
        self.print_section("1. Orphan Nodes")
        query = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN labels(n) AS node_type, n.id AS id, n.label AS label
        """
        orphans = self.run_query(query)
        if orphans:
            print("WARNING: Found orphan nodes:")
            self.print_json(orphans)
        else:
            print("No orphan nodes found. ✓")
        
        # 2. Check for subcategories without parents
        self.print_section("2. Subcategories Without Parents")
        query = """
        MATCH (s:Subcategory)
        WHERE NOT ()-[:PARENT_OF]->(s)
        RETURN s.id AS subcategory, s.label AS label
        """
        no_parents = self.run_query(query)
        if no_parents:
            print("WARNING: Found subcategories without parent relationships:")
            self.print_json(no_parents)
        else:
            print("All subcategories have proper parent relationships. ✓")
        
        # 3. Check for nodes without required properties
        self.print_section("3. Nodes Missing Required Properties")
        query = """
        MATCH (n)
        WHERE n.id IS NULL OR n.label IS NULL
        RETURN labels(n) AS node_type, n.id AS id, n.label AS label
        """
        missing_props = self.run_query(query)
        if missing_props:
            print("WARNING: Found nodes missing required properties:")
            self.print_json(missing_props)
        else:
            print("All nodes have required properties. ✓")
        
        # 4. Check for circular dependencies in the hierarchy
        self.print_section("4. Circular Hierarchy Dependencies")
        query = """
        MATCH path = (n)-[:PARENT_OF*2..10]->(n)
        RETURN [node IN nodes(path) | node.id] AS circular_path
        """
        circles = self.run_query(query)
        if circles:
            print("WARNING: Found circular dependencies in hierarchy:")
            self.print_json(circles)
        else:
            print("No circular dependencies found in hierarchy. ✓")
        
        # 5. Subcategories without regulatory connections
        self.print_section("5. Subcategories Without Regulatory Links")
        query = """
        MATCH (s:Subcategory)
        WHERE NOT (s)-[:REGULATED_BY]->() AND NOT (s)-[:REGULATED_UNDER]->()
        RETURN s.id AS subcategory, s.label AS label
        """
        unregulated = self.run_query(query)
        if unregulated:
            print("NOTE: Found subcategories without regulatory connections:")
            self.print_json(unregulated)
        else:
            print("All subcategories have proper regulatory links. ✓")
    
    def verify_taxonomy(self, root_node=None):
        """Run all verification steps for the taxonomy."""
        try:
            self.connect()
            
            self.analyze_taxonomy_structure(root_node)
            self.analyze_regulatory_structure()
            self.check_taxonomy_integrity()
            
            print("\nVerification complete!")
        finally:
            self.close()

def main():
    parser = argparse.ArgumentParser(description='Verify taxonomy in Neo4j')
    parser.add_argument('--root', '-r', type=str, default=None,
                      help='Root node id for taxonomy verification')
    parser.add_argument('--uri', '-u', type=str, default="bolt://localhost:7687",
                      help='Neo4j URI (default: bolt://localhost:7687)')
    parser.add_argument('--username', '-n', type=str, default="neo4j",
                      help='Neo4j username (default: neo4j)')
    parser.add_argument('--password', '-p', type=str, default="Rathum12!",
                      help='Neo4j password')
    parser.add_argument('--database', '-d', type=str, default="neo4j",
                      help='Neo4j database name (default: neo4j)')
    
    args = parser.parse_args()
    
    verifier = TaxonomyVerifier(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database
    )
    
    verifier.verify_taxonomy(args.root)

if __name__ == "__main__":
    main()