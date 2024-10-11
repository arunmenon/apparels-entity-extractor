import os
from dotenv import load_dotenv  # Import load_dotenv to load environment variables
from graph_db.graph_strategy_factory import GraphDatabaseFactory, get_query_type
from helpers.query_loader import load_queries_from_json  # Import from the helpers module

# Load environment variables from .env file
load_dotenv()

# Load environment variables
EXTRACTED_ENTITIES_DIR = os.getenv("EXTRACTED_ENTITIES_DIR")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 20))  # Default batch size to 20 if not set

# Process queries in batches
def process_queries_in_batches(graph_db_strategy, query_type):
    # Connect to the graph database
    graph_db_strategy.connect()

    # Optionally create the database if it doesn't exist
    graph_db_strategy.create_database_if_not_exists()

    # Load the queries based on the type (Cypher or GSQL)
    queries = load_queries_from_json(EXTRACTED_ENTITIES_DIR, query_type)

    # Execute the queries in batches
    for i in range(0, len(queries), BATCH_SIZE):
        batch = queries[i:i + BATCH_SIZE]
        graph_db_strategy.execute_batch(batch)
        print(f"Executed batch {i // BATCH_SIZE + 1}")

    # Close the connection
    graph_db_strategy.close()

if __name__ == "__main__":
    print("Starting graph query execution in batches...")

    # Load the appropriate graph database strategy using the factory
    graph_db_strategy = GraphDatabaseFactory.create_graph_database_strategy()

    # Determine the query type (Cypher or GSQL)
    query_type = get_query_type()

    # Process the queries
    process_queries_in_batches(graph_db_strategy, query_type)

    print("All queries executed successfully.")
