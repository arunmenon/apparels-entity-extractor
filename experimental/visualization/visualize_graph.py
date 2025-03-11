import os
import json
import re
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import glob

def extract_nodes_and_relationships(cypher_query):
    """
    Parse a Cypher query to extract nodes and relationships.
    """
    nodes = {}
    relationships = []
    
    # Extract nodes with labels from MERGE statements
    # Enhanced pattern to handle more complex Cypher queries
    node_pattern = r"MERGE\s+\((\w+):(\w+)\s+\{([^}]+)\}\)"
    for match in re.finditer(node_pattern, cypher_query):
        var_name, node_type, props = match.groups()
        # Extract name or description
        prop_pattern = r"name:\s*['\"]([^'\"]+)['\"]|description:\s*['\"]([^'\"]+)['\"]"
        prop_match = re.search(prop_pattern, props)
        if prop_match:
            node_name = prop_match.group(1) or prop_match.group(2)
            # Truncate long names for better visualization
            if node_name and len(node_name) > 50:
                node_name = node_name[:47] + "..."
            nodes[var_name] = {"type": node_type, "name": node_name}
        else:
            # For nodes without name/description, use a default
            nodes[var_name] = {"type": node_type, "name": f"{node_type}_{var_name}"}
    
    # Extract direct relationships
    rel_pattern = r"MERGE\s+\((\w+)\)-\[:(\w+)\]->\((\w+)\)"
    for match in re.finditer(rel_pattern, cypher_query):
        from_node, rel_type, to_node = match.groups()
        relationships.append((from_node, to_node, rel_type))
    
    # Extract relationships from UNWIND sections
    # Look for patterns inside UNWIND blocks - handle both PROHIBITS and ALLOWS
    if "PROHIBITS" in cypher_query:
        # We know there are PROHIBITS relationships
        # Find all blocks with rule definitions and link them to guideline
        rule_blocks = re.findall(r"UNWIND\s+\[(.*?)\]\s+AS\s+(\w+)", cypher_query, re.DOTALL)
        for block, var_name in rule_blocks:
            # Extract rules from this block
            rules = re.findall(r"{[^}]+status:\s+['\"](PROHIBITS|ALLOWS)['\"]", block)
            
            # Find the guideline node (usually 'g') and the rule node type
            if var_name == 'imp':
                rule_type = 'Imperium_Rule'
            elif var_name == 'pol':
                rule_type = 'Policy_Rule'
            elif var_name == 'img':
                rule_type = 'Image_Detection_Rule'
            else:
                rule_type = 'Rule'
                
            # Create the relationship for each rule
            rule_count = len(rules)
            for i, status in enumerate(rules):
                # Create a synthetic rule node name
                rule_node = f"{var_name}{i}"
                # Add rule node if it doesn't exist
                if rule_node not in nodes:
                    rule_desc = f"{rule_type}_{i+1}"
                    nodes[rule_node] = {"type": rule_type, "name": rule_desc}
                
                # Create relationship from guideline to rule
                relationships.append(('g', rule_node, status))
    
    # If we didn't find any relationships, try a more direct approach
    if not relationships:
        # Check for any HAS_SUB_CATEGORY or other relationships
        # This is a fallback for simpler Cypher queries
        has_category = re.search(r"MERGE\s+\((\w+)\)-\[:HAS_SUB_CATEGORY\]->\((\w+)\)", cypher_query)
        if has_category:
            from_node, to_node = has_category.groups()
            relationships.append((from_node, to_node, "HAS_SUB_CATEGORY"))
            
        has_guideline = re.search(r"MERGE\s+\((\w+)\)-\[:HAS_GUIDELINE\]->\((\w+)\)", cypher_query)
        if has_guideline:
            from_node, to_node = has_guideline.groups()
            relationships.append((from_node, to_node, "HAS_GUIDELINE"))
    
    return nodes, relationships

def build_graph_from_jsons(extracted_entities_dir):
    """
    Build a NetworkX graph from all JSON files in the given directory.
    """
    G = nx.DiGraph()
    
    # Process all JSON files
    json_files = glob.glob(os.path.join(extracted_entities_dir, "*.json"))
    
    # Track node types for coloring
    node_types = set()
    
    # Collect all nodes and relationships
    all_nodes = {}
    all_relationships = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if 'cypher_query' in data:
                    cypher_query = data['cypher_query']
                    nodes, relationships = extract_nodes_and_relationships(cypher_query)
                    
                    # Add to collections
                    all_nodes.update(nodes)
                    all_relationships.extend(relationships)
                    
                    # Keep track of node types
                    for node_info in nodes.values():
                        node_types.add(node_info["type"])
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    # Create a mapping from variable names to unique node identifiers
    node_mapping = {}
    for var_name, node_info in all_nodes.items():
        node_id = f"{node_info['type']}_{node_info['name']}"
        node_mapping[var_name] = node_id
        
        # Add node to graph with attributes
        G.add_node(node_id, 
                  label=node_info['name'], 
                  type=node_info['type'])
    
    # Add edges to graph
    for from_var, to_var, rel_type in all_relationships:
        if from_var in node_mapping and to_var in node_mapping:
            from_id = node_mapping[from_var]
            to_id = node_mapping[to_var]
            G.add_edge(from_id, to_id, relationship=rel_type)
    
    # Generate colors for node types
    colors = plt.cm.tab10(range(len(node_types)))
    color_map = {node_type: colors[i] for i, node_type in enumerate(node_types)}
    
    return G, color_map

def visualize_graph(G, color_map, output_file=None, layout_type="spring"):
    """
    Visualize the graph with node colors based on node type.
    """
    plt.figure(figsize=(20, 14))
    
    # Choose layout
    if layout_type == "spring":
        pos = nx.spring_layout(G, k=0.5, iterations=50)
    elif layout_type == "circular":
        pos = nx.circular_layout(G)
    elif layout_type == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G)
    
    # Draw nodes with colors based on node type
    for node_type, color in color_map.items():
        node_list = [node for node, attr in G.nodes(data=True) if attr.get('type') == node_type]
        nx.draw_networkx_nodes(G, pos, 
                              nodelist=node_list,
                              node_color=[to_rgba(color)],
                              node_size=300,
                              alpha=0.8)
    
    # Draw edges with different colors based on relationship type
    rel_types = set(nx.get_edge_attributes(G, 'relationship').values())
    edge_colors = plt.cm.Set3(range(len(rel_types)))
    edge_color_map = {rel_type: edge_colors[i] for i, rel_type in enumerate(rel_types)}
    
    for rel_type, color in edge_color_map.items():
        edge_list = [(u, v) for u, v, attr in G.edges(data=True) if attr.get('relationship') == rel_type]
        nx.draw_networkx_edges(G, pos,
                               edgelist=edge_list,
                               edge_color=[to_rgba(color)],
                               arrows=True,
                               width=1.5,
                               alpha=0.7)
    
    # Draw labels with smaller font size
    labels = nx.get_node_attributes(G, 'label')
    nx.draw_networkx_labels(G, pos, labels, font_size=8, font_family='sans-serif')
    
    # Create a legend for node types
    plt.figure(figsize=(6, 4))
    legend_elements = []
    for node_type, color in color_map.items():
        legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                         markerfacecolor=color, markersize=10, label=node_type))
    
    # Add relationship types to legend
    for rel_type, color in edge_color_map.items():
        legend_elements.append(plt.Line2D([0], [0], color=color, lw=2, label=f'Rel: {rel_type}'))
    
    plt.legend(handles=legend_elements, loc='center')
    plt.axis('off')
    
    # Save the legend to a file
    plt.savefig('graph_legend.png', dpi=300, bbox_inches='tight')
    
    # Return to the main plot
    plt.figure(1)
    plt.axis('off')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Graph visualization saved to {output_file}")
    else:
        plt.show()

def create_subgraphs_by_category(G):
    """
    Break down the full graph into smaller subgraphs by category.
    """
    # Get nodes with Offensive_Content_Category type
    categories = [node for node, attr in G.nodes(data=True) 
                 if attr.get('type') == 'Offensive_Content_Category']
    
    subgraphs = {}
    for category in categories:
        # Start with the category node
        category_nodes = {category}
        
        # Do a BFS to find all connected nodes
        to_visit = list(G.successors(category))
        visited = set(to_visit)
        
        while to_visit:
            current = to_visit.pop(0)
            category_nodes.add(current)
            
            for neighbor in G.successors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    to_visit.append(neighbor)
        
        # Create subgraph
        subgraph = G.subgraph(category_nodes)
        subgraphs[G.nodes[category]['label']] = subgraph
    
    return subgraphs

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize compliance entity graph')
    parser.add_argument('--limit', type=int, default=0, 
                        help='Limit the number of JSON files to process (0 for all)')
    parser.add_argument('--dir', type=str, default='extracted_entities',
                        help='Directory containing extracted JSON files')
    parser.add_argument('--output-dir', type=str, default='graph_visualizations',
                        help='Directory to save visualization files')
    parser.add_argument('--sample', action='store_true',
                        help='Process a sample of 3-5 JSON files for quick testing')
    args = parser.parse_args()
    
    extracted_entities_dir = args.dir
    output_dir = args.output_dir
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all JSON files
    json_files = glob.glob(os.path.join(extracted_entities_dir, "*.json"))
    
    # Apply limits if specified
    if args.sample:
        # Sample a few files for quick testing
        import random
        sample_size = min(5, len(json_files))
        json_files = random.sample(json_files, sample_size)
        print(f"Processing a sample of {sample_size} JSON files")
    elif args.limit > 0:
        json_files = json_files[:args.limit]
        print(f"Processing {len(json_files)} JSON files (limited to {args.limit})")
    else:
        print(f"Processing all {len(json_files)} JSON files")
    
    # Build the graph
    print("Building graph from extracted entities...")
    
    # Custom function to process specified files
    def build_graph_from_specific_jsons(file_list):
        G = nx.DiGraph()
        node_types = set()
        all_nodes = {}
        all_relationships = []
        
        for json_file in file_list:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if 'cypher_query' in data:
                        cypher_query = data['cypher_query']
                        nodes, relationships = extract_nodes_and_relationships(cypher_query)
                        
                        # Add to collections
                        all_nodes.update(nodes)
                        all_relationships.extend(relationships)
                        
                        # Keep track of node types
                        for node_info in nodes.values():
                            node_types.add(node_info["type"])
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
        
        # Create a mapping from variable names to unique node identifiers
        node_mapping = {}
        for var_name, node_info in all_nodes.items():
            node_id = f"{node_info['type']}_{node_info['name']}"
            node_mapping[var_name] = node_id
            
            # Add node to graph with attributes
            G.add_node(node_id, 
                    label=node_info['name'], 
                    type=node_info['type'])
        
        # Add edges to graph
        for from_var, to_var, rel_type in all_relationships:
            if from_var in node_mapping and to_var in node_mapping:
                from_id = node_mapping[from_var]
                to_id = node_mapping[to_var]
                G.add_edge(from_id, to_id, relationship=rel_type)
        
        # Generate colors for node types
        colors = plt.cm.tab10(range(len(node_types)))
        color_map = {node_type: colors[i] for i, node_type in enumerate(node_types)}
        
        return G, color_map
    
    G, color_map = build_graph_from_specific_jsons(json_files)
    
    print(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    
    # Save full graph visualization
    output_file = os.path.join(output_dir, "full_compliance_graph.png")
    visualize_graph(G, color_map, output_file=output_file, layout_type="spring")
    
    # Create and visualize subgraphs by category
    print("Creating category subgraphs...")
    subgraphs = create_subgraphs_by_category(G)
    
    for category_name, subgraph in subgraphs.items():
        # Clean filename by removing problematic characters
        safe_name = re.sub(r'[^\w\s-]', '', category_name).strip().replace(' ', '_')
        print(f"Visualizing subgraph for category '{category_name}' with {subgraph.number_of_nodes()} nodes")
        output_file = os.path.join(output_dir, f"category_{safe_name}_graph.png")
        visualize_graph(subgraph, color_map, 
                       output_file=output_file, 
                       layout_type="kamada_kawai")
    
    # Save legend in output directory
    legend_file = os.path.join(output_dir, "graph_legend.png")
    print(f"Legend saved to {legend_file}")
    
    print(f"\nAll graph visualizations saved to {output_dir}/")

if __name__ == "__main__":
    main()