#!/usr/bin/env python3
"""
Script to analyze entity context relationships across pages.
"""

import os
import json
import argparse
from pathlib import Path
import pandas as pd
from tabulate import tabulate
import networkx as nx
import matplotlib.pyplot as plt

def load_extracted_data(extracted_dir, pages):
    """Load extracted data for specific pages."""
    data = {}
    
    for page in pages:
        page_path = os.path.join(extracted_dir, f"extracted_{page}.json")
        if os.path.exists(page_path):
            with open(page_path, 'r') as f:
                try:
                    data[page] = json.load(f)
                except json.JSONDecodeError:
                    print(f"Error parsing JSON in {page_path}")
                    data[page] = {}
        else:
            print(f"File not found: {page_path}")
    
    return data

def build_entity_graph(data):
    """Build a graph of entity relationships across pages."""
    G = nx.DiGraph()
    
    # Track categories, subcategories, and rules
    categories = set()
    subcategories = {}  # subcat -> page
    guidelines = {}     # guideline -> (page, subcat)
    rules = {}          # rule -> (page, subcat)
    
    # Add nodes and edges
    for page, content in data.items():
        if not content:
            continue
            
        category = content.get("offensive_content_category", "")
        if category:
            G.add_node(category, type="category", page=page)
            categories.add(category)
            
        for subcat in content.get("sub_categories", []):
            G.add_node(subcat, type="subcategory", page=page)
            subcategories[subcat] = page
            
            # Connect subcategory to category
            if category:
                G.add_edge(category, subcat, type="has_subcategory")
            
        # Connect guidelines to subcategories
        for guideline in content.get("guidelines", []):
            desc = guideline.get("description", "")
            if desc:
                node_id = f"guideline: {desc[:50]}..."
                G.add_node(node_id, type="guideline", page=page, description=desc)
                guidelines[node_id] = (page, subcat)
                
                # Connect to subcategories
                for subcat in content.get("sub_categories", []):
                    G.add_edge(subcat, node_id, type="has_guideline")
        
        # Connect rules to subcategories
        for rule in content.get("rules", []):
            desc = rule.get("description", "")
            status = rule.get("status", "")
            rule_type = rule.get("type", "")
            
            if desc:
                node_id = f"rule: {rule_type} - {desc[:30]}... ({status})"
                G.add_node(node_id, type="rule", page=page, description=desc, 
                           status=status, rule_type=rule_type)
                rules[node_id] = (page, subcat)
                
                # Connect to subcategories
                for subcat in content.get("sub_categories", []):
                    G.add_edge(subcat, node_id, type="has_rule")
    
    return G, categories, subcategories, guidelines, rules

def analyze_context_flow(G, pages):
    """Analyze how context flows between pages."""
    # Find entities that span multiple pages
    multi_page_entities = {}
    
    # Check nodes that appear on multiple pages
    for node in G.nodes():
        node_data = G.nodes[node]
        if 'page' in node_data:
            entity_type = node_data.get('type', '')
            page = node_data.get('page', '')
            
            if entity_type and page:
                key = (entity_type, node)
                if key not in multi_page_entities:
                    multi_page_entities[key] = set()
                multi_page_entities[key].add(page)
    
    # Filter to only entities that span pages
    spanning_entities = {k: v for k, v in multi_page_entities.items() if len(v) > 1}
    
    # Analyze parent-child relationships across pages
    cross_page_relationships = []
    
    for source, target in G.edges():
        source_data = G.nodes[source]
        target_data = G.nodes[target]
        
        if 'page' in source_data and 'page' in target_data:
            source_page = source_data['page']
            target_page = target_data['page']
            
            if source_page != target_page:
                edge_type = G.edges[source, target].get('type', '')
                cross_page_relationships.append({
                    'source': source,
                    'source_type': source_data.get('type', ''),
                    'source_page': source_page,
                    'target': target,
                    'target_type': target_data.get('type', ''),
                    'target_page': target_page,
                    'relationship': edge_type
                })
    
    return spanning_entities, cross_page_relationships

def print_context_report(G, categories, subcategories, guidelines, rules, 
                         spanning_entities, cross_page_relationships):
    """Print a report on context relationships."""
    print("\n=== ENTITY CONTEXT ANALYSIS ===")
    
    # Basic stats
    print(f"\nBASIC STATISTICS:")
    print(f"Total Categories: {len(categories)}")
    print(f"Total Subcategories: {len(subcategories)}")
    print(f"Total Guidelines: {len(guidelines)}")
    print(f"Total Rules: {len(rules)}")
    print(f"Total Relationships: {G.number_of_edges()}")
    
    # Entities spanning multiple pages
    print(f"\nENTITIES SPANNING MULTIPLE PAGES ({len(spanning_entities)}):")
    if spanning_entities:
        for (entity_type, entity), pages in spanning_entities.items():
            print(f"- {entity_type}: \"{entity}\" appears on pages: {', '.join(sorted(pages))}")
    else:
        print("None found")
    
    # Cross-page relationships
    print(f"\nCROSS-PAGE RELATIONSHIPS ({len(cross_page_relationships)}):")
    if cross_page_relationships:
        for i, rel in enumerate(cross_page_relationships, 1):
            print(f"{i}. {rel['source_type']} \"{rel['source']}\" ({rel['source_page']}) "
                  f"→ {rel['relationship']} → "
                  f"{rel['target_type']} \"{rel['target']}\" ({rel['target_page']})")
    else:
        print("None found")
    
    # Category-Subcategory hierarchy
    print(f"\nCATEGORY-SUBCATEGORY HIERARCHY:")
    for category in sorted(categories):
        print(f"\n{category}")
        subcats = [n for n in G.successors(category) 
                   if G.nodes[n].get('type') == 'subcategory']
        for subcat in sorted(subcats):
            print(f"  └─ {subcat}")
            
            # Rules for this subcategory
            rules = [n for n in G.successors(subcat) 
                     if G.nodes[n].get('type') == 'rule']
            for rule in sorted(rules):
                status = G.nodes[rule].get('status', '')
                print(f"     └─ 🔒 {rule} [{status}]")
            
            # Guidelines for this subcategory
            guidelines = [n for n in G.successors(subcat) 
                          if G.nodes[n].get('type') == 'guideline']
            for guideline in sorted(guidelines):
                print(f"     └─ 📋 {guideline}")

def visualize_graph(G, output_dir, output_file):
    """Visualize the entity graph."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)
    
    # Set node colors based on type
    node_colors = []
    for node in G.nodes():
        node_type = G.nodes[node].get('type', '')
        if node_type == 'category':
            node_colors.append('skyblue')
        elif node_type == 'subcategory':
            node_colors.append('lightgreen')
        elif node_type == 'guideline':
            node_colors.append('orange')
        elif node_type == 'rule':
            node_colors.append('lightcoral')
        else:
            node_colors.append('gray')
    
    # Create the plot
    plt.figure(figsize=(12, 10))
    pos = nx.spring_layout(G, seed=42)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=300, alpha=0.8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, alpha=0.5, arrows=True)
    
    # Draw labels (simplified for readability)
    labels = {}
    for node in G.nodes():
        if G.nodes[node].get('type') == 'category':
            labels[node] = node
        elif G.nodes[node].get('type') == 'subcategory':
            labels[node] = node[:20] + '...' if len(node) > 20 else node
        elif G.nodes[node].get('type') in ['guideline', 'rule']:
            labels[node] = node[:15] + '...' if len(node) > 15 else node
    
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    
    # Create legend
    plt.plot([0], [0], color='skyblue', marker='o', markersize=10, linestyle='', label='Category')
    plt.plot([0], [0], color='lightgreen', marker='o', markersize=10, linestyle='', label='Subcategory')
    plt.plot([0], [0], color='orange', marker='o', markersize=10, linestyle='', label='Guideline')
    plt.plot([0], [0], color='lightcoral', marker='o', markersize=10, linestyle='', label='Rule')
    
    plt.legend(loc='upper right')
    plt.axis('off')
    plt.title('Entity Relationship Graph')
    plt.tight_layout()
    
    # Save the plot
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nGraph visualization saved to: {output_path}")

def save_context_data(G, spanning_entities, cross_page_relationships, 
                     output_dir, output_file):
    """Save context analysis data to file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)
    
    # Prepare data for serialization
    node_data = {}
    for node in G.nodes():
        node_data[str(node)] = {k: str(v) for k, v in G.nodes[node].items()}
    
    edge_data = []
    for source, target in G.edges():
        edge_data.append({
            'source': str(source),
            'target': str(target),
            'data': {k: str(v) for k, v in G.edges[source, target].items()}
        })
    
    # Convert spanning entities for serialization
    spanning_data = {}
    for (entity_type, entity), pages in spanning_entities.items():
        spanning_data[f"{entity_type}|{entity}"] = list(pages)
    
    data = {
        'nodes': node_data,
        'edges': edge_data,
        'spanning_entities': spanning_data,
        'cross_page_relationships': cross_page_relationships
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Context analysis data saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Analyze entity context relationships across pages')
    parser.add_argument('--pages', nargs='+', required=True, help='List of page names (e.g., page_1_toc page_1_details page_2)')
    parser.add_argument('--extracted-dir', default='extracted_entities', help='Directory containing extracted entity files')
    parser.add_argument('--output-dir', default='experimental/reporting/outputs', help='Directory to save reports')
    parser.add_argument('--data-file', default='context_analysis.json', help='Filename for context analysis data')
    parser.add_argument('--graph-file', default='entity_graph.png', help='Filename for graph visualization')
    
    args = parser.parse_args()
    
    # Load extracted data
    data = load_extracted_data(args.extracted_dir, args.pages)
    
    # Build entity graph
    G, categories, subcategories, guidelines, rules = build_entity_graph(data)
    
    # Analyze context flow
    spanning_entities, cross_page_relationships = analyze_context_flow(G, args.pages)
    
    # Print context report
    print_context_report(G, categories, subcategories, guidelines, rules, 
                         spanning_entities, cross_page_relationships)
    
    # Save context data
    save_context_data(G, spanning_entities, cross_page_relationships, 
                     args.output_dir, args.data_file)
    
    # Visualize graph
    try:
        visualize_graph(G, args.output_dir, args.graph_file)
    except Exception as e:
        print(f"Error generating graph visualization: {e}")

if __name__ == "__main__":
    main()