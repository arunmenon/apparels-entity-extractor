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
        # Escape single quotes by replacing them with escaped single quotes
        return value.replace("'", "\\'")
    return value

def sanitize_query(query):
    """
    Escapes single quotes inside the values of the {name: '...'} pattern in the query string.
    
    :param query: The query string to sanitize.
    :return: The sanitized query.
    """
    # Regular expression pattern to find {name: '...'} and capture content inside the single quotes
    pattern = r"\{name: '(.*?)'\}"

    # Define a function to escape the content inside the single quotes
    def escape_match(match):
        # Capture the part inside single quotes
        content = match.group(1)
        # Escape the content
        escaped_content = escape_special_characters(content)
        # Rebuild the {name: '...'} part with escaped content
        return f"{{name: '{escaped_content}'}}"

    # Apply the regex substitution to escape content inside {name: '...'}
    sanitized_query = re.sub(pattern, escape_match, query)

    return sanitized_query

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
