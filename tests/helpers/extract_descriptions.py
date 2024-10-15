import re

def extract_descriptions(query):
    """
    Extract all description blocks from the input query and return them in a list.
    """
    # Updated regular expression to capture text inside description, including nested single quotes
    pattern = r"description: '((?:[^']|\\')*)'"

    # Use a non-greedy match to capture full description with special characters
    matches = re.finditer(pattern, query)
    
    descriptions = []
    for match in matches:
        descriptions.append(match.group(1))
    
    return descriptions

def main():
    # Input query string
    query = """CREATE (n1:Apparel_Category {name: 'All Upper Body'})-[:HAS_PRODUCT_TYPE]->(n2:Product_Type {name: 'Tops'})-[:FOLLOWS_GUIDELINE]->(n3:Guideline_Type {name: 'Product Name Guidelines'})-[:HAS_formula]->(n4:formula {name: 'Naming Formula for Tops'}) WITH n1, n2, n3, n4 UNWIND [{step_name: 'Naming Formula for Tops', description: 'Brand Name \'or\' License Name (if applicable) + Style Name + Descriptive Feature/Clothing Top Style/Character/Sports League/Sports Team/Material, + Apparel Style + Clothing Type + Count Per Pack + (Clothing Size Group)'}] AS step CREATE (n4)-[:HAS_STEP]->(n5:Step {name: step.step_name, description: step.description})"""

    # Extract descriptions
    descriptions = extract_descriptions(query)
    
    # Print all the extracted descriptions
    for i, desc in enumerate(descriptions, 1):
        print(f"Description {i}: {desc}")

if __name__ == "__main__":
    main()
