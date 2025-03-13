#!/usr/bin/env python3
"""
Script to export Neo4j graph data to Cypher commands for recreating the graph elsewhere.
"""
import os
import json
from datetime import datetime
from neo4j import GraphDatabase

def connect_to_neo4j():
    """Connect to Neo4j database using environment variables."""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "Rathum12")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        return driver
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        return None

def get_all_node_labels(driver):
    """Get all node labels in the database."""
    with driver.session() as session:
        result = session.run("CALL db.labels()")
        return [record["label"] for record in result]

def get_all_relationship_types(driver):
    """Get all relationship types in the database."""
    with driver.session() as session:
        result = session.run("CALL db.relationshipTypes()")
        return [record["relationshipType"] for record in result]

def generate_create_node_queries(driver, label):
    """Generate Cypher queries to create all nodes with a specific label."""
    queries = []
    with driver.session() as session:
        result = session.run(f"MATCH (n:{label}) RETURN n")
        for record in result:
            node = record["n"]
            node_id = node.id
            props = dict(node.items())
            
            # Escape any special characters in string properties
            for key, value in props.items():
                if isinstance(value, str):
                    props[key] = value.replace("'", "\\'").replace('"', '\\"')
            
            props_str = json.dumps(props).replace('"', "'")
            queries.append(f"CREATE (n:{label} {props_str}) SET n._id = {node_id}")
    
    return queries

def generate_create_relationship_queries(driver, rel_type):
    """Generate Cypher queries to create relationships of a specific type."""
    queries = []
    with driver.session() as session:
        result = session.run(f"""
        MATCH (a)-[r:{rel_type}]->(b) 
        RETURN a, r, b
        """)
        
        for record in result:
            start_node = record["a"]
            rel = record["r"]
            end_node = record["b"]
            
            start_id = start_node.id
            end_id = end_node.id
            
            # Get relationship properties
            rel_props = dict(rel.items())
            for key, value in rel_props.items():
                if isinstance(value, str):
                    rel_props[key] = value.replace("'", "\\'").replace('"', '\\"')
            
            # Generate property string if properties exist
            if rel_props:
                props_str = json.dumps(rel_props).replace('"', "'")
                rel_query = f"MATCH (a), (b) WHERE a._id = {start_id} AND b._id = {end_id} CREATE (a)-[r:{rel_type} {props_str}]->(b)"
            else:
                rel_query = f"MATCH (a), (b) WHERE a._id = {start_id} AND b._id = {end_id} CREATE (a)-[r:{rel_type}]->(b)"
            
            queries.append(rel_query)
    
    return queries

def export_graph_to_cypher(output_file):
    """Export entire graph to Cypher queries in a file."""
    driver = connect_to_neo4j()
    if not driver:
        return
    
    try:
        node_labels = get_all_node_labels(driver)
        rel_types = get_all_relationship_types(driver)
        
        with open(output_file, 'w') as f:
            # Write header with timestamp
            f.write(f"// Neo4j graph export generated on {datetime.now()}\n")
            f.write("// First create all nodes, then create relationships\n\n")
            
            # Add index creation for _id
            f.write("// Create index for temporary node IDs\n")
            f.write("CREATE INDEX node_temp_id IF NOT EXISTS FOR (n) ON (n._id);\n\n")
            
            # Add constraint for unique _id
            f.write("// Add constraint for unique temporary IDs\n")
            f.write("CREATE CONSTRAINT temp_id_unique IF NOT EXISTS ON (n) ASSERT n._id IS UNIQUE;\n\n")
            
            # Generate node creation queries
            f.write("// Node creation queries\n")
            for label in node_labels:
                f.write(f"// Creating {label} nodes\n")
                node_queries = generate_create_node_queries(driver, label)
                for query in node_queries:
                    f.write(f"{query};\n")
                f.write("\n")
            
            # Generate relationship creation queries
            f.write("// Relationship creation queries\n")
            for rel_type in rel_types:
                f.write(f"// Creating {rel_type} relationships\n")
                rel_queries = generate_create_relationship_queries(driver, rel_type)
                for query in rel_queries:
                    f.write(f"{query};\n")
                f.write("\n")
            
            # Clean up temporary IDs
            f.write("// Remove temporary IDs and cleanup\n")
            f.write("MATCH (n) REMOVE n._id;\n")
            f.write("DROP INDEX node_temp_id IF EXISTS;\n")
            f.write("DROP CONSTRAINT temp_id_unique IF EXISTS;\n")
        
        print(f"Export completed. Cypher queries written to {output_file}")
    
    finally:
        driver.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Export Neo4j graph to Cypher queries")
    parser.add_argument("-o", "--output", default="graph_export.cypher", 
                        help="Output file path (default: graph_export.cypher)")
    args = parser.parse_args()
    
    export_graph_to_cypher(args.output)