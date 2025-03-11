import os
import json
import re
import glob
from collections import Counter

def extract_nodes_and_relationships(cypher_query):
    """
    Parse a Cypher query to extract nodes, relationships, and other stats.
    """
    # Stats to gather
    stats = {
        "node_types": [],
        "relationship_types": [],
        "prohibits_count": 0,
        "allows_count": 0,
        "attributes_count": 0
    }
    
    # Extract node types
    node_pattern = r"MERGE\s+\((\w+):(\w+)\s+\{"
    for match in re.finditer(node_pattern, cypher_query):
        var_name, node_type = match.groups()
        stats["node_types"].append(node_type)
    
    # Extract relationship types
    rel_pattern = r"MERGE\s+\(.*?\)-\[:(\w+)\]->"
    for match in re.finditer(rel_pattern, cypher_query):
        rel_type = match.group(1)
        stats["relationship_types"].append(rel_type)
    
    # Count PROHIBITS vs ALLOWS relationships
    if "PROHIBITS" in cypher_query:
        prohibits_count = len(re.findall(r"status:\s+['\"](PROHIBITS)['\"]", cypher_query))
        stats["prohibits_count"] += prohibits_count
    
    if "ALLOWS" in cypher_query:
        allows_count = len(re.findall(r"status:\s+['\"](ALLOWS)['\"]", cypher_query))
        stats["allows_count"] += allows_count
    
    # Count attributes
    attributes_pattern = r"MERGE\s+\(a:Attribute"
    stats["attributes_count"] = len(re.findall(attributes_pattern, cypher_query))
    
    return stats

def analyze_graph_data(extracted_entities_dir):
    """
    Analyze all the JSON files to gather graph statistics.
    """
    # Initialize counters and stats
    total_stats = {
        "total_files": 0,
        "node_types": Counter(),
        "relationship_types": Counter(),
        "prohibits_count": 0,
        "allows_count": 0,
        "attributes_count": 0,
        "categories": set(),
        "subcategories": set()
    }
    
    # Process all JSON files
    json_files = glob.glob(os.path.join(extracted_entities_dir, "*.json"))
    total_stats["total_files"] = len(json_files)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if 'cypher_query' in data:
                    cypher_query = data['cypher_query']
                    file_stats = extract_nodes_and_relationships(cypher_query)
                    
                    # Update counters
                    total_stats["node_types"].update(file_stats["node_types"])
                    total_stats["relationship_types"].update(file_stats["relationship_types"])
                    total_stats["prohibits_count"] += file_stats["prohibits_count"]
                    total_stats["allows_count"] += file_stats["allows_count"]
                    total_stats["attributes_count"] += file_stats["attributes_count"]
                    
                    # Extract categories and subcategories
                    category_pattern = r"Offensive_Content_Category\s+\{name:\s+['\"](.*?)['\"]"
                    subcategory_pattern = r"Sub_Category\s+\{name:\s+['\"](.*?)['\"]"
                    
                    categories = re.findall(category_pattern, cypher_query)
                    subcategories = re.findall(subcategory_pattern, cypher_query)
                    
                    total_stats["categories"].update(categories)
                    total_stats["subcategories"].update(subcategories)
                    
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    return total_stats

def print_graph_statistics(stats):
    """
    Print out formatted statistics about the graph.
    """
    print("=" * 50)
    print("COMPLIANCE KNOWLEDGE GRAPH STATISTICS")
    print("=" * 50)
    
    print(f"\nProcessed {stats['total_files']} entity extraction files")
    
    print("\nNode Types:")
    for node_type, count in stats["node_types"].most_common():
        print(f"  - {node_type}: {count}")
    
    print("\nRelationship Types:")
    for rel_type, count in stats["relationship_types"].most_common():
        print(f"  - {rel_type}: {count}")
    
    print("\nRule Statistics:")
    print(f"  - PROHIBITS relationships: {stats['prohibits_count']}")
    print(f"  - ALLOWS relationships: {stats['allows_count']}")
    print(f"  - Attributes: {stats['attributes_count']}")
    
    print("\nCategories:")
    for category in sorted(stats["categories"]):
        print(f"  - {category}")
    
    print("\nSubcategories:")
    for subcategory in sorted(stats["subcategories"]):
        print(f"  - {subcategory}")
    
    print("\nSummary:")
    print(f"  - Total node types: {len(stats['node_types'])}")
    print(f"  - Total nodes (approx): {sum(stats['node_types'].values())}")
    print(f"  - Total relationship types: {len(stats['relationship_types'])}")
    print(f"  - Total relationships (approx): {sum(stats['relationship_types'].values())}")
    print(f"  - Categories: {len(stats['categories'])}")
    print(f"  - Subcategories: {len(stats['subcategories'])}")
    print(f"  - Rules: {stats['prohibits_count'] + stats['allows_count']}")
    
    if stats['prohibits_count'] + stats['allows_count'] > 0:
        print("\nRules breakdown:")
        print(f"  - Prohibited: {stats['prohibits_count']} ({stats['prohibits_count']*100/(stats['prohibits_count']+stats['allows_count']):.1f}%)")
        print(f"  - Allowed: {stats['allows_count']} ({stats['allows_count']*100/(stats['prohibits_count']+stats['allows_count']):.1f}%)")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze compliance entity graph')
    parser.add_argument('--dir', type=str, default='extracted_entities',
                        help='Directory containing extracted JSON files')
    args = parser.parse_args()
    
    # Directory containing the extracted entities
    extracted_entities_dir = args.dir
    
    # Analyze the graph data
    stats = analyze_graph_data(extracted_entities_dir)
    
    # Print the statistics
    print_graph_statistics(stats)

if __name__ == "__main__":
    main()