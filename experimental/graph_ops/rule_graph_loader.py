import os
import json
import re
from dotenv import load_dotenv
from graph_db.graph_strategy_factory import GraphDatabaseFactory, get_query_type

# Load environment variables
load_dotenv()

# Constants
PARSED_RULES_DIR = os.getenv("PARSED_RULES_DIR", "parsed_rules")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 20))

def sanitize_name(name):
    """Sanitize a name for use in Cypher queries"""
    if name is None:
        return "unknown"
    
    # Remove special characters, replace with underscore
    sanitized = re.sub(r'[^\w\s]', '_', str(name))
    # Replace spaces with underscore
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = 'n' + sanitized
    
    return sanitized

def generate_cypher_for_rule_metadata(rule_metadata):
    """
    Generate Cypher query to create rule metadata nodes and relationships
    
    Args:
        rule_metadata: Dictionary containing rule metadata
    
    Returns:
        Cypher query string
    """
    rule_id = rule_metadata.get("rule_id")
    rule_name = rule_metadata.get("rule_name", "").replace('"', '\\"')
    rule_description = rule_metadata.get("rule_description", "").replace('"', '\\"')
    policy_name = rule_metadata.get("policy_name", "").replace('"', '\\"')
    policy_group = rule_metadata.get("policy_group", "").replace('"', '\\"')
    rule_priority = rule_metadata.get("rule_priority", "")
    rule_type = rule_metadata.get("rule_type", "")
    
    # Create unique identifiers for nodes
    rule_id_sanitized = sanitize_name(rule_id)
    policy_name_sanitized = sanitize_name(policy_name)
    policy_group_sanitized = sanitize_name(policy_group)
    
    cypher = f"""
    // Create rule node
    MERGE (rule:Imperium_Rule {{rule_id: "{rule_id}"}})
    ON CREATE SET
      rule.name = "{rule_name}",
      rule.description = "{rule_description}",
      rule.version = {rule_metadata.get("rule_version", 1)},
      rule.start_date = "{rule_metadata.get("start_date", "")}",
      rule.end_date = "{rule_metadata.get("end_date", "")}",
      rule.status = "{rule_metadata.get("rule_status", "")}",
      rule.global_filter = "{rule_metadata.get("global_filter", "")}",
      rule.local_filter = "{rule_metadata.get("local_filter", "")}",
      rule.action = "{rule_metadata.get("action", "")}",
      rule.reason_code = "{rule_metadata.get("reason_code", "")}"
    
    // Create policy group node
    MERGE (pg:Policy_Group {{name: "{policy_group}"}})
    
    // Create policy name node
    MERGE (pn:Policy_Name {{name: "{policy_name}"}})
    
    // Create rule type node
    MERGE (rt:Rule_Type {{type: "{rule_type}"}})
    
    // Create rule priority node
    MERGE (rp:Rule_Priority {{level: "{rule_priority}"}})
    
    // Create relationships
    MERGE (rule)-[:HAS_POLICY_GROUP]->(pg)
    MERGE (rule)-[:HAS_POLICY_NAME]->(pn)
    MERGE (rule)-[:HAS_TYPE]->(rt)
    MERGE (rule)-[:HAS_PRIORITY]->(rp)
    MERGE (pn)-[:BELONGS_TO_GROUP]->(pg)
    """
    
    return cypher

def generate_cypher_for_expression_node(node, parent_ref=None, node_id=1):
    """
    Recursively generate Cypher for an expression tree node
    
    Args:
        node: The current node in the expression tree
        parent_ref: Reference to the parent node (for creating relationships)
        node_id: Unique identifier for this node
    
    Returns:
        Tuple of (cypher_query, next_node_id)
    """
    if not node:
        return "", node_id
    
    node_type = node.get("type")
    current_ref = f"n{node_id}"
    next_id = node_id + 1
    
    cypher = ""
    
    if node_type == "LOGICAL":
        operator = node.get("operator")
        cypher += f"""
        CREATE ({current_ref}:Logical_Operator {{type: "{operator}"}})
        """
        
        if parent_ref:
            cypher += f"""
            CREATE ({parent_ref})-[:HAS_CONDITION]->({current_ref})
            """
        
        conditions = node.get("conditions", [])
        for condition in conditions:
            condition_cypher, next_id = generate_cypher_for_expression_node(
                condition, current_ref, next_id
            )
            cypher += condition_cypher
    
    elif node_type == "COMPARISON":
        field = node.get("field", "").replace('"', '\\"')
        operator = node.get("operator", "").replace('"', '\\"')
        values = node.get("values", [])
        
        # Create comparison node
        cypher += f"""
        CREATE ({current_ref}:Comparison {{field: "{field}", operator: "{operator}"}})
        """
        
        if parent_ref:
            cypher += f"""
            CREATE ({parent_ref})-[:HAS_CONDITION]->({current_ref})
            """
        
        # Create field node if not exists and link to comparison
        field_ref = f"f{next_id}"
        next_id += 1
        cypher += f"""
        MERGE (field_{field_ref}:Field {{name: "{field}"}})
        CREATE ({current_ref})-[:HAS_FIELD]->(field_{field_ref})
        """
        
        # Create operator node if not exists and link to comparison
        op_ref = f"op{next_id}"
        next_id += 1
        cypher += f"""
        MERGE (op_{op_ref}:Operator {{type: "{operator}"}})
        CREATE ({current_ref})-[:HAS_OPERATOR]->(op_{op_ref})
        """
        
        # Create value nodes and link to comparison
        for i, value in enumerate(values):
            value_str = str(value).replace('"', '\\"')
            value_ref = f"v{next_id}"
            next_id += 1
            
            cypher += f"""
            CREATE ({value_ref}:Value {{content: "{value_str}"}})
            CREATE ({current_ref})-[:HAS_VALUE]->({value_ref})
            """
    
    return cypher, next_id

def generate_cypher_for_rule(rule_json):
    """
    Generate complete Cypher query for a rule and its expression tree
    
    Args:
        rule_json: Complete rule JSON including metadata and expression tree
    
    Returns:
        Cypher query string
    """
    rule_metadata = rule_json.get("rule_metadata", {})
    expression_tree = rule_json.get("expression_tree", {})
    rule_id = rule_metadata.get("rule_id")
    
    # Generate metadata cypher
    metadata_cypher = generate_cypher_for_rule_metadata(rule_metadata)
    
    # Generate expression tree cypher
    rule_ref = f"rule"
    expression_cypher, _ = generate_cypher_for_expression_node(
        expression_tree, rule_ref, 1
    )
    
    # Combine all Cypher
    full_cypher = f"""
    // Rule {rule_id} - {rule_metadata.get('rule_name')}
    {metadata_cypher}
    {expression_cypher}
    """
    
    return full_cypher

def load_rule_into_graph(graph_db_strategy, rule_json):
    """
    Load a single rule into the graph database
    
    Args:
        graph_db_strategy: The graph database strategy to use
        rule_json: The rule JSON to load
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate Cypher query
        cypher_query = generate_cypher_for_rule(rule_json)
        
        # Execute Cypher query
        graph_db_strategy.execute_query(cypher_query)
        
        return True
    except Exception as e:
        rule_id = rule_json.get("rule_metadata", {}).get("rule_id", "unknown")
        print(f"Error loading rule {rule_id} into graph: {e}")
        return False

def create_indexes(graph_db_strategy):
    """
    Create necessary indexes for efficient querying
    
    Args:
        graph_db_strategy: The graph database strategy to use
    """
    if graph_db_strategy.__class__.__name__ == "Neo4jDatabase":
        # Neo4j-specific indexes
        index_queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Imperium_Rule) ON (n.rule_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Policy_Group) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Policy_Name) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Rule_Type) ON (n.type)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Rule_Priority) ON (n.level)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Field) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Operator) ON (n.type)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Value) ON (n.content)"
        ]
        
        # Connect and create indexes
        graph_db_strategy.connect()
        graph_db_strategy.execute_batch(index_queries)
        graph_db_strategy.close()
        print("Created indexes for Imperium rules schema")

def load_rules_into_graph(num_rules=None):
    """
    Load parsed rules into the graph database
    
    Args:
        num_rules: Maximum number of rules to load (None for all)
    """
    try:
        # Get list of parsed rule files
        rule_files = [f for f in os.listdir(PARSED_RULES_DIR) if f.endswith('.json')]
        
        # Limit number of rules if specified
        if num_rules is not None:
            rule_files = rule_files[:num_rules]
        
        print(f"Loading {len(rule_files)} rules into graph database...")
        
        # Connect to the graph database (real or mock)
        graph_db_strategy = GraphDatabaseFactory.create_graph_database_strategy()
            
        # Create indexes if using Neo4j
        if graph_db_strategy.__class__.__name__ == "Neo4jDatabase":
            create_indexes(graph_db_strategy)
            
        # Connect to database
        graph_db_strategy.connect()
        
        # Check if we're using MockDatabase
        is_mock = graph_db_strategy.__class__.__name__ == "MockDatabase"
        if is_mock:
            print("Running in MOCK mode - Cypher queries will be displayed but not executed")
        
        # Process rules in batches
        success_count = 0
        for i, rule_file in enumerate(rule_files):
            try:
                file_path = os.path.join(PARSED_RULES_DIR, rule_file)
                
                # Load rule JSON
                with open(file_path, 'r') as f:
                    rule_json = json.load(f)
                
                # Get rule ID
                rule_id = rule_json.get("rule_metadata", {}).get("rule_id", "unknown")
                print(f"Processing rule {rule_id} ({i+1}/{len(rule_files)})")
                
                # Generate Cypher query
                cypher_query = generate_cypher_for_rule(rule_json)
                
                if is_mock:
                    # Display the query in full for mock mode
                    print(f"\n=== CYPHER QUERY for Rule {rule_id} ===")
                    print(cypher_query)
                    print("===================================\n")
                    
                # Execute the query using the database strategy
                graph_db_strategy.execute_query(cypher_query)
                success_count += 1
                
                # Commit every BATCH_SIZE rules
                if (i + 1) % BATCH_SIZE == 0:
                    print(f"Committed batch {(i + 1) // BATCH_SIZE}")
            
            except Exception as e:
                print(f"Error processing rule file {rule_file}: {e}")
        
        # Close connection
        graph_db_strategy.close()
        
        print(f"Successfully processed {success_count}/{len(rule_files)} rules")
        
    except Exception as e:
        print(f"Error loading rules into graph: {e}")
        
    # Return the number of successfully processed rules
    return success_count

if __name__ == "__main__":
    # Check if parsed rules directory exists
    if not os.path.exists(PARSED_RULES_DIR):
        print(f"Error: Parsed rules directory '{PARSED_RULES_DIR}' does not exist")
        print("Please run rule_expression_parser.py first to generate parsed rules")
        exit(1)
    
    # Load rules into graph
    load_rules_into_graph(num_rules=10)  # Limit to 10 rules for testing