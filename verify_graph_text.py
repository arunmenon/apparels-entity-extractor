import os
import json
import time
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

def verify_graph():
    """Verify the graph structure and print detailed information"""
    print("Verifying Neo4j Graph Structure...\n")
    
    # Query 1: Count nodes by label
    count_query = """
    MATCH (n)
    RETURN labels(n)[0] as label, count(*) as count
    ORDER BY count DESC
    """
    
    # Query 2: Show rule details
    rule_query = """
    MATCH (r:Imperium_Rule)
    RETURN r.rule_id, r.name, r.description, r.action
    """
    
    # Query 3: Look at policy metadata
    policy_query = """
    MATCH (pg:Policy_Group)<-[:HAS_POLICY_GROUP]-(r:Imperium_Rule)-[:HAS_POLICY_NAME]->(pn:Policy_Name)
    RETURN pg.name as policy_group, pn.name as policy_name, count(r) as rule_count
    """
    
    # Query 4: Examine rule structure
    structure_query = """
    MATCH (r:Imperium_Rule)-[:HAS_CONDITION*]->(c:Comparison)
    RETURN r.rule_id, count(c) as condition_count
    """
    
    # Query 5: Look at field types and values used
    fields_query = """
    MATCH (f:Field)<-[:HAS_FIELD]-(c:Comparison)
    RETURN f.name as field, count(c) as usage_count
    ORDER BY usage_count DESC
    """
    
    # Query 6: Check value distributions
    values_query = """
    MATCH (v:Value)<-[:HAS_VALUE]-(c:Comparison)-[:HAS_FIELD]->(f:Field)
    RETURN f.name as field, count(v) as value_count
    ORDER BY value_count DESC
    """
    
    # Run the queries and display results
    print("=== Node Counts by Type ===")
    counts = run_query(count_query)
    for record in counts:
        print(f"{record['label']}: {record['count']} nodes")
    
    print("\n=== Rules in Database ===")
    rules = run_query(rule_query)
    for rule in rules:
        print(f"Rule {rule['r.rule_id']}: {rule['r.name']} - {rule['r.action']}")
        print(f"  Description: {rule['r.description']}")
    
    print("\n=== Policy Information ===")
    policies = run_query(policy_query)
    for policy in policies:
        print(f"Policy Group: {policy['policy_group']}, Policy Name: {policy['policy_name']}")
        print(f"  Associated with {policy['rule_count']} rules")
    
    print("\n=== Rule Complexity ===")
    structures = run_query(structure_query)
    for structure in structures:
        print(f"Rule {structure['r.rule_id']} has {structure['condition_count']} conditions")
    
    print("\n=== Fields Usage ===")
    fields = run_query(fields_query)
    for field in fields:
        print(f"Field {field['field']} used in {field['usage_count']} conditions")
    
    print("\n=== Value Counts by Field ===")
    values = run_query(values_query)
    for value in values:
        print(f"Field {value['field']} has {value['value_count']} values")
    
    # Check detailed structure of one rule if any exist
    if rules:
        rule_id = rules[0]['r.rule_id']
        print(f"\n=== Detailed Structure for Rule {rule_id} ===")
        
        # Get conditions
        conditions_query = f"""
        MATCH (rule:Imperium_Rule {{rule_id: "{rule_id}"}})-[:HAS_CONDITION*]->(c:Comparison)
        OPTIONAL MATCH (c)-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (c)-[:HAS_OPERATOR]->(o:Operator)
        OPTIONAL MATCH (c)-[:HAS_VALUE]->(v:Value)
        RETURN c.field as field, o.type as operator, collect(v.content) as values
        """
        
        conditions = run_query(conditions_query)
        for i, condition in enumerate(conditions):
            values_str = ", ".join([f'"{v}"' for v in condition["values"]])
            print(f"  {i+1}. {condition['field']} {condition['operator']} [{values_str}]")
        
        # Get policy and metadata
        metadata_query = f"""
        MATCH (rule:Imperium_Rule {{rule_id: "{rule_id}"}})
        OPTIONAL MATCH (rule)-[:HAS_POLICY_GROUP]->(pg:Policy_Group)
        OPTIONAL MATCH (rule)-[:HAS_POLICY_NAME]->(pn:Policy_Name)
        OPTIONAL MATCH (rule)-[:HAS_PRIORITY]->(rp:Rule_Priority)
        OPTIONAL MATCH (rule)-[:HAS_TYPE]->(rt:Rule_Type)
        RETURN pg.name as policy_group, pn.name as policy_name, 
               rp.level as priority, rt.type as rule_type
        """
        
        metadata = run_query(metadata_query)
        if metadata:
            md = metadata[0]
            print(f"  Policy Group: {md['policy_group']}")
            print(f"  Policy Name: {md['policy_name']}")
            print(f"  Priority: {md['priority']}")
            print(f"  Rule Type: {md['rule_type']}")
    
    print("\nVerification complete!")

if __name__ == "__main__":
    verify_graph()