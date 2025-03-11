import os
import json
import pandas as pd
from dotenv import load_dotenv
from graph_db.graph_strategy_factory import GraphDatabaseFactory

# Load environment variables
load_dotenv()

# Define constants
EXCEL_PATH = os.path.expanduser("~/Downloads/Rules.xlsx")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))

def load_rules_from_excel(excel_path):
    """
    Load rules from Excel file
    
    Args:
        excel_path: Path to the Excel file
    
    Returns:
        Pandas DataFrame with the rules
    """
    print(f"Loading rules from {excel_path}...")
    df = pd.read_excel(excel_path)
    print(f"Loaded {len(df)} rules from Excel")
    return df

def generate_cypher_for_rule(rule):
    """
    Generate Cypher query for a rule
    
    Args:
        rule: Pandas Series representing a rule
    
    Returns:
        Cypher query string
    """
    # Extract rule metadata
    rule_id = rule["Rule_Id"]
    rule_name = rule["Rule_Name"].replace('"', '\\"')
    rule_description = rule["Rule_Description"].replace('"', '\\"') if pd.notna(rule["Rule_Description"]) else ""
    rule_version = rule["Rule_Version"]
    start_date = rule["Start_Date"].strftime("%Y-%m-%d") if pd.notna(rule["Start_Date"]) else ""
    end_date = rule["End_Date"].strftime("%Y-%m-%d") if pd.notna(rule["End_Date"]) else ""
    rule_status = rule["Rule_Status"] if pd.notna(rule["Rule_Status"]) else ""
    global_filter = rule["Global_Filter"] if pd.notna(rule["Global_Filter"]) else ""
    local_filter = rule["Local_Filter"] if pd.notna(rule["Local_Filter"]) else ""
    policy_name = rule["PolicyName"].replace('"', '\\"') if pd.notna(rule["PolicyName"]) else ""
    policy_group = rule["PolicyGroup"].replace('"', '\\"') if pd.notna(rule["PolicyGroup"]) else ""
    rule_priority = rule["RulePriority"] if pd.notna(rule["RulePriority"]) else ""
    rule_type = rule["RuleType"] if pd.notna(rule["RuleType"]) else ""
    action = rule["Action"] if pd.notna(rule["Action"]) else ""
    reason_code = rule["Reason Code"].replace('"', '\\"') if pd.notna(rule["Reason Code"]) else ""
    constraints = str(rule["Constraints"]).replace('"', '\\"') if pd.notna(rule["Constraints"]) else ""
    
    # Simplified rule expression for now - not parsing the complex structure
    rule_expression = str(rule["Rule_Expression"]).replace('"', '\\"') if pd.notna(rule["Rule_Expression"]) else ""
    
    # Create Cypher query
    cypher = f"""
    // Create rule node
    MERGE (rule:Imperium_Rule {{rule_id: "{rule_id}"}})
    ON CREATE SET
      rule.name = "{rule_name}",
      rule.description = "{rule_description}",
      rule.version = {rule_version},
      rule.start_date = "{start_date}",
      rule.end_date = "{end_date}",
      rule.status = "{rule_status}",
      rule.global_filter = "{global_filter}",
      rule.local_filter = "{local_filter}",
      rule.action = "{action}",
      rule.reason_code = "{reason_code}",
      rule.constraints = "{constraints}",
      rule.rule_expression = "{rule_expression}"
    
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

def process_rules_in_batches(rules_df):
    """
    Process rules in batches
    
    Args:
        rules_df: Pandas DataFrame with the rules
    """
    print(f"Processing {len(rules_df)} rules in batches of {BATCH_SIZE}...")
    
    # Connect to graph database
    graph_db_strategy = GraphDatabaseFactory.create_graph_database_strategy()
    graph_db_strategy.connect()
    
    # Create indexes
    create_indexes(graph_db_strategy)
    
    # Process in batches
    total_rules = len(rules_df)
    success_count = 0
    
    for i in range(0, total_rules, BATCH_SIZE):
        batch = rules_df.iloc[i:i+BATCH_SIZE]
        print(f"Processing batch {i//BATCH_SIZE + 1}/{(total_rules-1)//BATCH_SIZE + 1} ({len(batch)} rules)...")
        
        # Generate Cypher queries for batch
        queries = []
        for _, rule in batch.iterrows():
            query = generate_cypher_for_rule(rule)
            queries.append(query)
        
        # Execute batch
        try:
            graph_db_strategy.execute_batch(queries)
            success_count += len(batch)
            print(f"Successfully processed batch {i//BATCH_SIZE + 1}")
        except Exception as e:
            print(f"Error processing batch {i//BATCH_SIZE + 1}: {e}")
    
    # Close connection
    graph_db_strategy.close()
    
    print(f"Successfully processed {success_count}/{total_rules} rules")

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
            "CREATE INDEX IF NOT EXISTS FOR (n:Rule_Priority) ON (n.level)"
        ]
        
        # Connect and create indexes
        graph_db_strategy.execute_batch(index_queries)
        print("Created indexes for Imperium rules schema")

def main():
    """
    Main function to process rules from Excel and load into graph database
    """
    # Load rules from Excel
    rules_df = load_rules_from_excel(EXCEL_PATH)
    
    # Process rules in batches
    process_rules_in_batches(rules_df)
    
    print("\nRules processing completed successfully!")

if __name__ == "__main__":
    main()