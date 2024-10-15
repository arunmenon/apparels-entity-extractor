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
    Sanitizes both the {name: '...'} and {description: '...'} patterns in the query string.
    
    :param query: The query string to sanitize.
    :return: The sanitized query.
    """
    query = sanitize_query_name(query)
    query = sanitize_query_desc(query)
    return query

def sanitize_query_name(query):
    """
    Escapes single quotes inside the values of the {name: '...'} pattern in the query string.
    
    :param query: The query string to sanitize.
    :return: The sanitized query.
    """
    # Regular expression pattern to find {name: '...'} and capture content inside the single quotes
    pattern = r"\{name: '(.*?)'\}"

    # Define a function to escape the content inside the single quotes
    def escape_match(match):
        content = match.group(1)
        escaped_content = escape_special_characters(content)
        return f"{{name: '{escaped_content}'}}"

    sanitized_query = re.sub(pattern, escape_match, query)
    return sanitized_query

def sanitize_query_desc(query):
    """
    Escapes single quotes inside the values of the {description: '...'} pattern in the query string.
    
    :param query: The query string to sanitize.
    :return: The sanitized query.
    """
    # More precise regex to handle inner single quotes correctly inside the description
    pattern = r"\{description: '((?:[^'\\]|\\.)*)'\}"

    # Define a function to escape the content inside the single quotes
    def escape_match(match):
        content = match.group(1)
        escaped_content = escape_special_characters(content)
        return f"{{description: '{escaped_content}'}}"

    sanitized_query = re.sub(pattern, escape_match, query)
    return sanitized_query

# Test cases
def test_sanitize_query():
    test_cases = [
        {
            "input": "CREATE (n1:Apparel_Category {description: 'Brand Name 'or' License Name (if applicable)'})",
            "expected": "CREATE (n1:Apparel_Category {description: 'Brand Name \\'or\\' License Name (if applicable)'})"
        },
        {
            "input": "CREATE (n1:Apparel_Category {description: 'Men's jackets: stylish and warm.'})",
            "expected": "CREATE (n1:Apparel_Category {description: 'Men\\'s jackets: stylish and warm.'})"
        },
        {
            "input": "CREATE (n1:Apparel_Category {name: 'All Upper Body'})-[:HAS_PRODUCT_TYPE]->(n2:Product_Type {name: 'Tops'})-[:FOLLOWS_GUIDELINE]->(n3:Guideline_Type {name: 'Product Name Guidelines'})-[:HAS_formula]->(n4:formula {name: 'Naming Formula for Tops'}) WITH n1, n2, n3, n4 UNWIND [{step_name: 'Naming Formula for Tops', description: 'Brand Name 'or' License Name (if applicable) + Style Name + Descriptive Feature/Clothing Top Style/Character/Sports League/Sports Team/Material, + Apparel Style + Clothing Type + Count Per Pack + (Clothing Size Group)'}] AS step CREATE (n4)-[:HAS_STEP]->(n5:Step {name: step.step_name, description: step.description})",
            "expected": "CREATE (n1:Apparel_Category {name: 'All Upper Body'})-[:HAS_PRODUCT_TYPE]->(n2:Product_Type {name: 'Tops'})-[:FOLLOWS_GUIDELINE]->(n3:Guideline_Type {name: 'Product Name Guidelines'})-[:HAS_formula]->(n4:formula {name: 'Naming Formula for Tops'}) WITH n1, n2, n3, n4 UNWIND [{step_name: 'Naming Formula for Tops', description: 'Brand Name \\'or\\' License Name (if applicable) + Style Name + Descriptive Feature/Clothing Top Style/Character/Sports League/Sports Team/Material, + Apparel Style + Clothing Type + Count Per Pack + (Clothing Size Group)'}] AS step CREATE (n4)-[:HAS_STEP]->(n5:Step {name: step.step_name, description: step.description})"
        }
    ]

    for i, case in enumerate(test_cases, 1):
        input_query = case["input"]
        expected_result = case["expected"]
        print(f"\n--- Test Case {i} ---")
        print(f"Input query: {input_query}")
        result = sanitize_query(input_query)
        print(f"Sanitized query: {result}")
        print(f"Expected result: {expected_result}")
        print(f"Test passed: {result == expected_result}")

# Run the tests
if __name__ == "__main__":
    test_sanitize_query()
