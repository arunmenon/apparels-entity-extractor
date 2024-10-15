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

    def execute_batch(self, queries):
        print(f"Executing batch with {len(queries)} queries...")
        attempted_queries = []
        failed_queries = []

        # Create a timestamped log file name for failed queries
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_queries_log = f"failed_queries_{timestamp}.log"  # Log file with timestamp

        with self.driver.session(database=self.database) as session:
            try:
                with session.begin_transaction() as tx:
                    for query in queries:
                        try:
                            #print(f"Executing query: {query}")
                            tx.run(query)
                            attempted_queries.append(query)
                        except Exception as e:
                            #print(f"Error executing query: {query}")
                            #print(f"Exception: {e}")
                            failed_queries.append(query)
                            # Log the failed query to a separate file for review
                            with open(failed_queries_log, "a") as log_file:
                                log_file.write(f"Failed query:\n{query}\nError: {str(e)}\n\n")
                    tx.commit()
            except Exception as tx_error:
                #print(f"Transaction failed, rolling back. Exception: {tx_error}")
                # At this point, rollback happens automatically in Neo4j
                #print(f"Rolling back the transaction. Attempted queries before failure: {attempted_queries}")
                 print(f"Rolling back the transaction.")
        # Summary of batch execution
        print(f"Completed executing batch. Successful queries: {len(attempted_queries) - len(failed_queries)}")
        print(f"Failed queries: {len(failed_queries)} (Logged in {failed_queries_log})")

    def close(self):
        if self.driver:
            self.driver.close()
            print("Neo4j connection closed.")
