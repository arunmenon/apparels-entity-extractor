import os
import json
import matplotlib.pyplot as plt
import networkx as nx
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

def create_rule_json(rule_id="12345"):
    """Create a JSON representation of the rule structure"""
    # Get all the data for the specified rule
    query = f"""
    MATCH (rule:Imperium_Rule {{rule_id: "{rule_id}"}})
    OPTIONAL MATCH (rule)-[:HAS_POLICY_GROUP]->(pg:Policy_Group)
    OPTIONAL MATCH (rule)-[:HAS_POLICY_NAME]->(pn:Policy_Name)
    OPTIONAL MATCH (rule)-[:HAS_PRIORITY]->(rp:Rule_Priority)
    OPTIONAL MATCH (rule)-[:HAS_TYPE]->(rt:Rule_Type)
    
    WITH rule, pg, pn, rp, rt
    
    MATCH (rule)-[:HAS_CONDITION]->(logic:Logical_Operator)
    
    WITH rule, pg, pn, rp, rt, logic
    
    OPTIONAL MATCH (logic)-[:HAS_CONDITION*]->(comp:Comparison)
    OPTIONAL MATCH (comp)-[:HAS_FIELD]->(field:Field)
    OPTIONAL MATCH (comp)-[:HAS_OPERATOR]->(op:Operator)
    OPTIONAL MATCH (comp)-[:HAS_VALUE]->(val:Value)
    
    RETURN 
        rule.rule_id as rule_id,
        rule.name as rule_name,
        rule.description as rule_description,
        pg.name as policy_group,
        pn.name as policy_name,
        rp.level as priority,
        rt.type as rule_type,
        logic.type as logic_type,
        comp.field as comp_field,
        op.type as operator,
        collect(val.content) as values
    """
    
    results = run_query(query)
    
    # Create the rule structure
    rule_data = {
        "rule_id": rule_id,
        "name": results[0]["rule_name"] if results else "Unknown",
        "description": results[0]["rule_description"] if results else "Unknown",
        "policy_group": results[0]["policy_group"] if results else "Unknown",
        "policy_name": results[0]["policy_name"] if results else "Unknown",
        "priority": results[0]["priority"] if results else "Unknown",
        "rule_type": results[0]["rule_type"] if results else "Unknown",
        "logic_type": results[0]["logic_type"] if results else "Unknown",
        "conditions": []
    }
    
    # Add conditions
    conditions_added = set()
    for result in results:
        comp_field = result["comp_field"]
        if comp_field and comp_field not in conditions_added:
            conditions_added.add(comp_field)
            rule_data["conditions"].append({
                "field": comp_field,
                "operator": result["operator"],
                "values": result["values"]
            })
    
    # Create output directory
    output_dir = "output_json"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to file
    output_path = os.path.join(output_dir, f"rule_{rule_id}.json")
    with open(output_path, 'w') as f:
        json.dump(rule_data, f, indent=2)
    
    print(f"Rule data exported to {output_path}")
    return rule_data

def create_simple_graph_visualization(rule_data):
    """Create a simple visualization of the rule structure"""
    # Create graph
    G = nx.DiGraph()
    
    # Add rule node
    rule_id = rule_data["rule_id"]
    rule_name = rule_data["name"]
    G.add_node(f"rule_{rule_id}", label=f"Rule: {rule_name}", type="Rule")
    
    # Add metadata nodes
    G.add_node("policy_group", label=f"Policy Group: {rule_data['policy_group']}", type="Metadata")
    G.add_node("policy_name", label=f"Policy Name: {rule_data['policy_name']}", type="Metadata")
    G.add_node("priority", label=f"Priority: {rule_data['priority']}", type="Metadata")
    G.add_node("rule_type", label=f"Type: {rule_data['rule_type']}", type="Metadata")
    
    # Add metadata edges
    G.add_edge(f"rule_{rule_id}", "policy_group", label="HAS_POLICY_GROUP")
    G.add_edge(f"rule_{rule_id}", "policy_name", label="HAS_POLICY_NAME")
    G.add_edge(f"rule_{rule_id}", "priority", label="HAS_PRIORITY")
    G.add_edge(f"rule_{rule_id}", "rule_type", label="HAS_TYPE")
    
    # Add logical operator
    logic_node = f"logic_{rule_data['logic_type']}"
    G.add_node(logic_node, label=f"Logical: {rule_data['logic_type']}", type="Logical")
    G.add_edge(f"rule_{rule_id}", logic_node, label="HAS_CONDITION")
    
    # Add conditions
    for i, condition in enumerate(rule_data["conditions"]):
        field = condition["field"]
        operator = condition["operator"]
        values = condition["values"]
        
        # Add comparison node
        comp_node = f"comp_{i}"
        G.add_node(comp_node, label=f"Comparison: {field}", type="Comparison")
        G.add_edge(logic_node, comp_node, label="HAS_CONDITION")
        
        # Add field node
        field_node = f"field_{field}"
        G.add_node(field_node, label=f"Field: {field}", type="Field")
        G.add_edge(comp_node, field_node, label="HAS_FIELD")
        
        # Add operator node
        op_node = f"op_{operator}"
        G.add_node(op_node, label=f"Operator: {operator}", type="Operator")
        G.add_edge(comp_node, op_node, label="HAS_OPERATOR")
        
        # Add value nodes
        for j, value in enumerate(values):
            value_node = f"value_{i}_{j}"
            G.add_node(value_node, label=f"Value: {value}", type="Value")
            G.add_edge(comp_node, value_node, label="HAS_VALUE")
    
    # Plot the graph
    plt.figure(figsize=(14, 10))
    
    # Define node colors by type
    node_colors = {
        'Rule': 'red',
        'Metadata': 'lightblue',
        'Logical': 'lightgreen',
        'Comparison': 'orange',
        'Field': 'purple',
        'Operator': 'brown',
        'Value': 'pink'
    }
    
    # Set node colors
    colors = [node_colors[G.nodes[node]['type']] for node in G.nodes]
    
    # Create the layout
    pos = nx.spring_layout(G, k=0.3, iterations=50)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_size=1500, node_color=colors, alpha=0.8)
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, arrows=True)
    
    # Add labels
    node_labels = {node: G.nodes[node]['label'] for node in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)
    
    # Add edge labels
    edge_labels = {(u, v): G[u][v]['label'] for u, v in G.edges}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
    
    plt.title(f"Graph Structure for Rule {rule_id}")
    plt.axis("off")
    
    # Save the figure
    output_dir = "output_images"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"rule_{rule_id}_simple_graph.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    
    print(f"Graph visualization saved to {output_path}")
    return output_path

def main():
    """Main function"""
    rule_id = "12345"  # The rule ID to visualize
    
    # Create the JSON representation
    rule_data = create_rule_json(rule_id)
    
    # Create a visualization
    graph_path = create_simple_graph_visualization(rule_data)
    
    # Print the rule data
    print("\nRule Data:")
    print(json.dumps(rule_data, indent=2))
    
    print(f"\nVisualization saved to {graph_path}")

if __name__ == "__main__":
    main()