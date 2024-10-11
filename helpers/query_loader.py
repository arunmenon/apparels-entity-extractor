import os
import json
import re

def escape_special_characters(value):
    """
    Escapes single quotes inside a string.
    
    :param value: The string value to escape.
    :return: The escaped string.
    """
    if isinstance(value, str):
        # Escape single quotes inside the string by replacing them with escaped single quotes
        return value.replace("'", "\\'")
    return value

def sanitize_query(query):
    """
    Escapes single quotes inside the values of the query string.
    
    :param query: The query string to sanitize.
    :return: The sanitized query.
    """
    # Split the query by single quotes to isolate the parts inside quotes
    parts = query.split("'")
    
    # Only escape the parts that are inside the quotes (odd indices)
    for i in range(1, len(parts), 2):
        parts[i] = escape_special_characters(parts[i])
    
    # Rejoin the parts together to form the sanitized query
    return "'".join(parts)

def load_queries_from_json(directory, query_type):
    """
    Load queries of the specified type (Cypher or GSQL) from JSON files, applying special character escaping.
    
    :param directory: The directory containing JSON files.
    :param query_type: The type of query to load ('cypher' or 'gsql').
    :return: A list of queries extracted from the JSON files with special characters escaped.
    """
    queries = []
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            with open(os.path.join(directory, filename), "r") as f:
                data = json.load(f)
                if "graph" in data:
                    for graph_data in data["graph"]:
                        key = f"linkage_{query_type}"
                        if key in graph_data:
                            # Sanitize query by escaping special characters
                            query = sanitize_query(graph_data[key])
                            queries.append(query)
    return queries
