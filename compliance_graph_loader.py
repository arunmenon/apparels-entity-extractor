import os
import json
from dotenv import load_dotenv  # Import load_dotenv to load environment variables
from graph_db.graph_strategy_factory import GraphDatabaseFactory, get_query_type
from helpers.query_loader import load_queries_from_json  # Import from the helpers module
from entity_context_manager import EntityContextManager

# Load environment variables from .env file
load_dotenv()

# Load environment variables
EXTRACTED_ENTITIES_DIR = os.getenv("EXTRACTED_ENTITIES_DIR", "extracted_entities")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 20))  # Default batch size to 20 if not set
CONTEXT_FILE = os.getenv("CONTEXT_FILE", "compliance_context.json")

# Initialize context manager
context_manager = EntityContextManager(CONTEXT_FILE)

# Process queries in batches with context awareness
def process_compliance_queries_in_batches(graph_db_strategy, query_type):
    """Process compliance-related queries in batches with context awareness."""
    # Connect to the graph database
    graph_db_strategy.connect()

    # Optionally create the database if it doesn't exist
    graph_db_strategy.create_database_if_not_exists()

    # Load the queries with context awareness
    queries = load_contextual_queries_from_json(EXTRACTED_ENTITIES_DIR, query_type)

    # Execute the queries in batches
    for i in range(0, len(queries), BATCH_SIZE):
        batch = queries[i:i + BATCH_SIZE]
        graph_db_strategy.execute_batch(batch)
        print(f"Executed compliance batch {i // BATCH_SIZE + 1}")

    # Close the connection
    graph_db_strategy.close()

def load_contextual_queries_from_json(directory, query_type):
    """
    Load queries with context-aware processing to handle missing parent nodes.
    This function enhances the original load_queries_from_json with context awareness.
    """
    queries = []
    
    # Get a sorted list of JSON files to ensure we process them in order by page number
    json_files = [f for f in os.listdir(directory) if f.endswith(".json")]
    json_files.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]) 
                    if "_" in x and x.split("_")[-1].split(".")[0].isdigit() else 0)
    
    for filename in json_files:
        try:
            with open(os.path.join(directory, filename), "r") as f:
                data = json.load(f)
                
                # Extract the cypher query from the data
                if 'cypher_query' in data:
                    cypher_query = data['cypher_query']
                    # The cypher query has already been enriched with context during extraction
                    queries.append(cypher_query)
                else:
                    print(f"Warning: No cypher_query found in {filename}")
                
        except Exception as e:
            print(f"Error processing file {filename}: {e}")
    
    return queries

def create_compliance_indexes(graph_db_strategy):
    """Create indexes for compliance schema to improve performance."""
    if graph_db_strategy.__class__.__name__ == "Neo4jDatabase":
        # Neo4j-specific indexes
        index_queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Offensive_Content_Category) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Sub_Category) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Guideline) ON (n.description)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Imperium_Rule) ON (n.rule_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Policy_Rule) ON (n.description)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Image_Detection_Rule) ON (n.description)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Attribute) ON (n.type, n.value)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Visual_Example) ON (n.classification)"
        ]
        
        # Connect and create indexes
        graph_db_strategy.connect()
        graph_db_strategy.execute_batch(index_queries)
        graph_db_strategy.close()
        print("Created compliance schema indexes")

def process_orphaned_rules(graph_db_strategy):
    """Process any orphaned rules that couldn't be attached during extraction."""
    # Get orphaned rules cypher from the context manager
    orphaned_rules_cypher = context_manager.generate_cypher_for_orphaned_rules()
    
    if orphaned_rules_cypher and len(orphaned_rules_cypher) > 0:
        print(f"Processing {len(orphaned_rules_cypher)} orphaned rules...")
        
        # Connect to the database
        graph_db_strategy.connect()
        
        # Execute the orphaned rules cypher in batches
        for i in range(0, len(orphaned_rules_cypher), BATCH_SIZE):
            batch = orphaned_rules_cypher[i:i + BATCH_SIZE]
            graph_db_strategy.execute_batch(batch)
            print(f"Executed orphaned rules batch {i // BATCH_SIZE + 1}")
        
        # Close the connection
        graph_db_strategy.close()
        print("All orphaned rules processed.")
    else:
        print("No orphaned rules to process.")

if __name__ == "__main__":
    print("Starting compliance graph query execution in batches with context awareness...")

    # Load the appropriate graph database strategy using the factory
    graph_db_strategy = GraphDatabaseFactory.create_graph_database_strategy()

    # Create indexes for better performance
    create_compliance_indexes(graph_db_strategy)

    # Determine the query type (Cypher or GSQL)
    query_type = get_query_type()

    # Process the main queries
    process_compliance_queries_in_batches(graph_db_strategy, query_type)
    
    # Process any orphaned rules
    process_orphaned_rules(graph_db_strategy)

    print("All compliance queries executed successfully with context awareness.")
