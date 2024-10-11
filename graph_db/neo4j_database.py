from neo4j import GraphDatabase
from graph_db.graph_interface import GraphDatabaseStrategy

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
        with self.driver.session(database=self.database) as session:
            with session.begin_transaction() as tx:
                for query in queries:
                    print(f"Executing query: {query}")
                    tx.run(query)
                tx.commit()

    def close(self):
        if self.driver:
            self.driver.close()
