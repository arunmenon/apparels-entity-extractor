import os
import json
import re
import glob
import argparse

def normalize_categories(json_dir, primary_category=None):
    """
    Normalize all categories in extracted JSON files to a single primary category.
    If primary_category is not provided, use the first one found.
    """
    # Get all JSON files in the directory
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    
    if not json_files:
        print(f"No JSON files found in {json_dir}")
        return False
    
    # If primary_category is not set, find the most frequent category in the files
    if not primary_category:
        categories = {}
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if 'cypher_query' in data:
                        cypher_query = data['cypher_query']
                        
                        # Find category in the query
                        category_pattern = r"MERGE \(occ:Offensive_Content_Category \{name: '([^']+)'\}\)"
                        category_matches = re.findall(category_pattern, cypher_query)
                        
                        for category in category_matches:
                            if category in categories:
                                categories[category] += 1
                            else:
                                categories[category] = 1
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
        
        # Use the most frequent category as the primary
        if categories:
            primary_category = max(categories, key=categories.get)
            print(f"Using most frequent category '{primary_category}' as the primary category")
        else:
            print("No categories found in JSON files")
            return False
    
    # Normalize all JSON files to use the primary category
    modified_files = 0
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
                if 'cypher_query' in data:
                    cypher_query = data['cypher_query']
                    
                    # Replace all category references with the primary category
                    category_pattern = r"MERGE \(occ:Offensive_Content_Category \{name: '([^']+)'\}\)"
                    matches = re.findall(category_pattern, cypher_query)
                    
                    if matches and any(cat != primary_category for cat in matches):
                        # Replace all occurrences with the primary category
                        normalized_query = re.sub(
                            category_pattern,
                            f"MERGE (occ:Offensive_Content_Category {{name: '{primary_category}'}})",
                            cypher_query
                        )
                        
                        # Update the data and save it back
                        if normalized_query != cypher_query:
                            data['cypher_query'] = normalized_query
                            with open(json_file, 'w') as f:
                                json.dump(data, f, indent=4)
                            modified_files += 1
                            print(f"Normalized category in {os.path.basename(json_file)}")
        except Exception as e:
            print(f"Error normalizing {json_file}: {e}")
    
    print(f"\nNormalization complete. Modified {modified_files} of {len(json_files)} files.")
    print(f"All files now use the primary category: '{primary_category}'")
    return True

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Normalize categories in extracted JSON files')
    parser.add_argument('--dir', type=str, default='extracted_entities_final',
                        help='Directory containing extracted JSON files')
    parser.add_argument('--category', type=str, default=None,
                        help='Primary category name to use (if not provided, will use most frequent)')
    
    args = parser.parse_args()
    
    # Normalize the categories
    normalize_categories(args.dir, args.category)

if __name__ == "__main__":
    main()