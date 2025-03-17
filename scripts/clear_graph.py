import os
try:
    from dotenv import load_dotenv
    # Load environment variables
    load_dotenv()
except ImportError:
    # Continue even if dotenv is not available
    pass
from neo4j import GraphDatabase

def run_query(query):
    """Run a query against the Neo4j database"""
    uri = "bolt://localhost:7687"  # Hardcoded URI
    user = "neo4j"  # Hardcoded user
    password = "Rathum12!"  # Hardcoded password
    
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            result = session.run(query)
            return result

def clear_graph():
    """Clear the graph database of all Imperium rule related nodes"""
    print("Clearing Neo4j database of all Imperium rule related nodes...")
    
    # Step 1: Delete all relationships first
    delete_all_rels_query = """
    MATCH ()-[r]->() DELETE r
    """
    run_query(delete_all_rels_query)
    print("Deleted all relationships")
    
    # Step 2: Delete all nodes
    delete_all_nodes_query = """
    MATCH (n) DELETE n
    """
    run_query(delete_all_nodes_query)
    print("Deleted all nodes")
    
    print("Neo4j database has been cleared of all Imperium rule related nodes")

if __name__ == "__main__":
    clear_graph()