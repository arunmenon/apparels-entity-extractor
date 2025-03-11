from neo4j import GraphDatabase
from graph_db.graph_interface import GraphDatabaseStrategy
import os
from datetime import datetime

class Neo4jDatabase(GraphDatabaseStrategy):
    def __init__(self, uri, username, password, database):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None

    def connect(self):
        print("Connecting to Neo4j...")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        print("Connected successfully!")

    def create_database_if_not_exists(self):
        # Skip database creation for Neo4j Community Edition
        print("Skipping database creation. Make sure you're using the default 'neo4j' database in the Community Edition.")

    def execute_query(self, query):
        """Execute a single query."""
        print(f"Executing query (first 100 chars): {query[:100]}...")
        success = False
        
        with self.driver.session(database=self.database) as session:
            try:
                result = session.run(query)
                success = True
                print("Query executed successfully")
            except Exception as e:
                print(f"Error executing query: {str(e)}")
                # Log the failed query to a separate file for review
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                failed_query_log = f"failed_query_{timestamp}.log"
                with open(failed_query_log, "a") as log_file:
                    log_file.write(f"Failed query:\n{query}\nError: {str(e)}\n\n")
        
        return success
    
    def execute_batch(self, queries):
        print(f"Executing batch with {len(queries)} queries...")
        successful_queries = 0
        failed_queries = 0

        # Create a timestamped log file name for failed queries
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_queries_log = f"failed_queries_{timestamp}.log"  # Log file with timestamp

        # Execute each query in its own transaction to prevent one failure from affecting others
        with self.driver.session(database=self.database) as session:
            for query in queries:
                try:
                    # Execute the query in its own transaction
                    result = session.run(query)
                    # Record the result
                    successful_queries += 1
                except Exception as e:
                    failed_queries += 1
                    # Log the failed query to a separate file for review
                    with open(failed_queries_log, "a") as log_file:
                        log_file.write(f"Failed query:\n{query}\nError: {str(e)}\n\n")
                    
                    # Print detailed error for debugging
                    print(f"Error executing query (first 100 chars): {query[:100]}...")
                    print(f"Exception: {e}")
        
        # Summary of batch execution
        print(f"Completed executing batch. Successful queries: {successful_queries}")
        print(f"Failed queries: {failed_queries} (Logged in {failed_queries_log})")

    def close(self):
        if self.driver:
            self.driver.close()
            print("Neo4j connection closed.")
