import os
from graph_db.neo4j_database import Neo4jDatabase
from graph_db.tigergraph_database import TigerGraphDatabase

class GraphDatabaseFactory:
    @staticmethod
    def create_graph_database_strategy():
        """Factory method to create a graph database strategy based on the environment configuration."""
        graph_db_type = os.getenv("GRAPH_DB_TYPE", "neo4j").lower()

        if graph_db_type == "neo4j":
            neo4j_uri = os.getenv("NEO4J_URI")
            neo4j_username = os.getenv("NEO4J_USERNAME")
            neo4j_password = os.getenv("NEO4J_PASSWORD")
            neo4j_database = os.getenv("NEO4J_DATABASE_NAME")
            return Neo4jDatabase(neo4j_uri, neo4j_username, neo4j_password, neo4j_database)

        elif graph_db_type == "tigergraph":
            tigergraph_host = os.getenv("TIGERGRAPH_HOST")
            tigergraph_username = os.getenv("TIGERGRAPH_USERNAME")
            tigergraph_password = os.getenv("TIGERGRAPH_PASSWORD")
            tigergraph_database = os.getenv("TIGERGRAPH_DATABASE")
            return TigerGraphDatabase(tigergraph_host, tigergraph_username, tigergraph_password, tigergraph_database)

        else:
            raise ValueError(f"Unsupported graph database type: {graph_db_type}")

def get_query_type():
    """Get the type of query to be used, either 'cypher' or 'gsql'."""
    query_type = os.getenv("QUERY_TYPE", "cypher").lower()
    if query_type not in ["cypher", "gsql"]:
        raise ValueError(f"Unsupported query type: {query_type}")
    return query_type
