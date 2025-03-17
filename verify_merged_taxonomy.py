#!/usr/bin/env python3
"""
Verify Merged Weapons Taxonomy

This script runs Cypher queries to verify the hierarchical structure and 
relationships in the merged weapons taxonomy graph.
"""

import os
import sys
import json
from neo4j import GraphDatabase

# Neo4j connection settings
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "Rathum12!"
neo4j_database = "neo4j"

def run_query(query, params=None):
    """Run a query against the Neo4j database and return results."""
    with GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)) as driver:
        with driver.session(database=neo4j_database) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_json(data):
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2))

def verify_taxonomy():
    print_section("Verifying Merged Weapons Taxonomy")
    
    # 1. Count nodes by type
    print_section("1. Node Counts by Type")
    query = """
    MATCH (n)
    RETURN labels(n) AS node_type, count(*) AS count
    ORDER BY count DESC
    """
    result = run_query(query)
    print_json(result)
    
    # 2. Count relationships by type
    print_section("2. Relationship Counts by Type")
    query = """
    MATCH ()-[r]->()
    RETURN type(r) AS relationship_type, count(*) AS count
    ORDER BY count DESC
    """
    result = run_query(query)
    print_json(result)
    
    # 3. List all top-level subcategories (directly under Weapons)
    print_section("3. Top-Level Weapon Categories")
    query = """
    MATCH (c:Category {id: 'Weapons'})-[:PARENT_OF]->(s:Subcategory)
    RETURN s.id AS category, s.label AS description
    ORDER BY category
    """
    result = run_query(query)
    print_json(result)
    
    # 4. Show hierarchical structure for Firearms
    print_section("4. Firearms Hierarchy")
    query = """
    MATCH path = (root:Category {id: 'Weapons'})-[:PARENT_OF*1..5]->(subcategory:Subcategory)
    WHERE root.id = 'Weapons' AND subcategory.id STARTS WITH 'Fire'
    WITH subcategory, length(path) AS depth
    MATCH p = (parent)-[:PARENT_OF]->(subcategory)
    WHERE parent:Category OR parent:Subcategory
    RETURN subcategory.id AS subcategory, parent.id AS parent, depth
    ORDER BY depth, subcategory
    """
    result = run_query(query)
    print_json(result)
    
    # 5. Show hierarchical structure for Blades (Knives & Swords)
    print_section("5. Blades Hierarchy")
    query = """
    MATCH path = (root)-[:PARENT_OF*1..5]->(subcategory:Subcategory)
    WHERE root.id = 'Weapons' AND (subcategory.id CONTAINS 'Blades' OR subcategory.id CONTAINS 'Knives' 
                                OR subcategory.id CONTAINS 'Sword' OR subcategory.id = 'Blunt Weapons'
                                OR subcategory.id = 'Flexible Weapons' OR subcategory.id CONTAINS 'Bladed')
    WITH subcategory, length(path) AS depth
    MATCH p = (parent)-[:PARENT_OF]->(subcategory)
    WHERE parent:Category OR parent:Subcategory
    RETURN subcategory.id AS subcategory, parent.id AS parent, depth
    ORDER BY depth, subcategory
    """
    result = run_query(query)
    print_json(result)
    
    # 6. Show hierarchical structure for Self-Defense Tools
    print_section("6. Self-Defense Tools Hierarchy")
    query = """
    MATCH path = (root)-[:PARENT_OF*1..5]->(subcategory:Subcategory)
    WHERE root.id = 'Weapons' AND (subcategory.id = 'Self-Defense Tools' OR subcategory.id CONTAINS 'Less-Lethal'
                                  OR subcategory.id CONTAINS 'Stun' OR subcategory.id CONTAINS 'Spray'
                                  OR subcategory.id CONTAINS 'Tear Gas' OR subcategory.id CONTAINS 'Rubber'
                                  OR subcategory.id CONTAINS 'Bean Bag')
    WITH subcategory, length(path) AS depth
    MATCH p = (parent)-[:PARENT_OF]->(subcategory)
    WHERE parent:Category OR parent:Subcategory
    RETURN subcategory.id AS subcategory, parent.id AS parent, depth
    ORDER BY depth, subcategory
    """
    result = run_query(query)
    print_json(result)
    
    # 7. Show hierarchical structure for Explosives & Incendiaries
    print_section("7. Explosives & Incendiaries Hierarchy")
    query = """
    MATCH path = (root)-[:PARENT_OF*1..5]->(subcategory:Subcategory)
    WHERE root.id = 'Weapons' AND (subcategory.id = 'Explosives & Incendiaries' OR subcategory.id CONTAINS 'Grenade'
                                 OR subcategory.id CONTAINS 'Bomb' OR subcategory.id CONTAINS 'Mine'
                                 OR subcategory.id CONTAINS 'IED' OR subcategory.id CONTAINS 'Explosive')
    WITH subcategory, length(path) AS depth
    MATCH p = (parent)-[:PARENT_OF]->(subcategory)
    WHERE parent:Category OR parent:Subcategory
    RETURN subcategory.id AS subcategory, parent.id AS parent, depth
    ORDER BY depth, subcategory
    """
    result = run_query(query)
    print_json(result)
    
    # 8. Show compliance areas for a specific weapon type
    print_section("8. Compliance Areas for Firearms")
    query = """
    MATCH (s:Subcategory {id: 'Firearms'})-[r:REGULATED_BY]->(ca:ComplianceArea)
    RETURN ca.id AS compliance_area,
           r.notes AS regulations
    ORDER BY compliance_area
    """
    result = run_query(query)
    print_json(result)
    
    # 9. Show laws governing a specific compliance area
    print_section("9. Laws Governing Trade Compliance")
    query = """
    MATCH (ca:ComplianceArea {id: 'Trade Compliance'})-[r:GOVERNED_BY]->(l:Law_Regulation)
    RETURN l.id AS law, 
           l.label AS full_name, 
           r.scope AS scope
    ORDER BY law
    """
    result = run_query(query)
    print_json(result)
    
    # 10. Find complete path from weapon category to laws
    print_section("10. Complete Regulatory Path for Firearms")
    query = """
    MATCH path = (s:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)
                 -[:GOVERNED_BY]->(l:Law_Regulation)
    RETURN s.id AS subcategory, ca.id AS compliance_area, l.id AS law
    ORDER BY ca.id, l.id
    """
    result = run_query(query)
    print_json(result)
    
    print("\nVerification complete!")

if __name__ == "__main__":
    verify_taxonomy()