import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

def run_query(query):
    """Run a query against the Neo4j database"""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            result = session.run(query)
            return list(result)

def main():
    """Main function to query the graph database"""
    
    # Query for rules
    rule_query = """
    MATCH (r:Imperium_Rule)
    RETURN r.rule_id, r.name, r.description LIMIT 10
    """
    
    # Query for rule structure
    structure_query = """
    MATCH (r:Imperium_Rule {rule_id: "12345"})-[:HAS_CONDITION]->(l:Logical_Operator)
    WITH r, l
    MATCH path = (l)-[:HAS_CONDITION*1..5]->()
    RETURN r.rule_id, r.name, l.type, count(path) as complexity
    """
    
    # Query for fields and values
    fields_query = """
    MATCH (r:Imperium_Rule {rule_id: "12345"})
    WITH r
    MATCH (r)-[:HAS_CONDITION*]->(c:Comparison)-[:HAS_FIELD]->(f:Field)
    RETURN DISTINCT f.name as field
    """
    
    print("Rules in database:")
    rules = run_query(rule_query)
    for rule in rules:
        print(f"- Rule {rule['r.rule_id']}: {rule['r.name']} - {rule['r.description']}")
    
    print("\nRule structure:")
    structure = run_query(structure_query)
    for s in structure:
        print(f"- Rule {s['r.rule_id']} ({s['r.name']}): {s['l.type']} operator with {s['complexity']} conditions")
    
    print("\nFields used in rule conditions:")
    fields = run_query(fields_query)
    for field in fields:
        print(f"- {field['field']}")

if __name__ == "__main__":
    main()