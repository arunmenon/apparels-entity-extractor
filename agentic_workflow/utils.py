from PIL import Image
import base64
import os
import json
import re

def save_image(image: Image.Image, path: str):
    """Saves a PIL image to a file."""
    image.save(path)
    print(f"Image saved to {path}.")

def encode_image(image_path):
    """Encodes an image as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def fix_relationship_types_in_queries(entities_dir):
    """
    Fix issues with dynamic relationship types in Cypher queries.
    Specifically replaces patterns like 'MERGE (g)-[rImp:imp.status]->(ir)' with
    the correct format 'MERGE (g)-[rImp:PROHIBITS]->(ir)' or 'MERGE (g)-[rImp:ALLOWS]->(ir)'
    
    Args:
        entities_dir: Directory containing the extracted JSON files
    """
    # Get all JSON files in the directory
    json_files = [f for f in os.listdir(entities_dir) if f.endswith(".json")]
    json_files.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]) 
                    if "_" in x and x.split("_")[-1].split(".")[0].isdigit() else 0)
    
    # Process each file
    for filename in json_files:
        file_path = os.path.join(entities_dir, filename)
        print(f"Processing {file_path}...")
        
        try:
            # Read the JSON file
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if 'cypher_query' in data:
                cypher_query = data['cypher_query']
                
                # Fix relationship type patterns
                # Pattern 1: MERGE (g)-[rImp:imp.status]->(ir)
                pattern1 = r'MERGE\s*\(g\)-\[rImp:imp\.status\]->\(ir\)'
                fixed_query = re.sub(pattern1, r'MERGE (g)-[rImp:PROHIBITS]->(ir)', cypher_query)
                
                # Pattern 2: MERGE (g)-[rPol:pol.status]->(pr)
                pattern2 = r'MERGE\s*\(g\)-\[rPol:pol\.status\]->\(pr\)'
                fixed_query = re.sub(pattern2, r'MERGE (g)-[rPol:PROHIBITS]->(pr)', fixed_query)
                
                # Pattern 3: MERGE (g)-[rImg:img.status]->(idr)
                pattern3 = r'MERGE\s*\(g\)-\[rImg:img\.status\]->\(idr\)'
                fixed_query = re.sub(pattern3, r'MERGE (g)-[rImg:PROHIBITS]->(idr)', fixed_query)
                
                # Check if the query changed
                if fixed_query != cypher_query:
                    print(f"  Fixed relationship types in {filename}")
                    
                    # Update the data and write it back
                    data['cypher_query'] = fixed_query
                    with open(file_path, 'w') as f:
                        json.dump(data, f, indent=4)
                else:
                    print(f"  No relationship type issues found in {filename}")
        
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
    
    print("Finished processing all JSON files.")

if __name__ == "__main__":
    # Example usage
    entities_dir = "extracted_entities"
    fix_relationship_types_in_queries(entities_dir)