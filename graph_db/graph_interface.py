from abc import ABC, abstractmethod

class GraphDatabaseStrategy(ABC):
    @abstractmethod
    def connect(self):
        """Connect to the graph database."""
        pass

    @abstractmethod
    def create_database_if_not_exists(self):
        """Create the database if it doesn't exist."""
        pass

    @abstractmethod
    def execute_batch(self, queries):
        """Execute a batch of queries."""
        pass

    @abstractmethod
    def close(self):
        """Close the connection."""
        pass
