#!/usr/bin/env python3
"""
Script to analyze and visualize category inheritance across pages.
"""

import os
import json
import argparse
from pathlib import Path
import pandas as pd
from tabulate import tabulate
import matplotlib.pyplot as plt
import networkx as nx

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

def analyze_inheritance(data):
    """Analyze category inheritance across pages."""
    pages = sorted(data.keys())
    
    # Track categories and subcategories by page
    categories = {}  # page -> category
    subcategories = {}  # page -> [subcats]
    
    # First pass: collect categories and subcategories
    for page in pages:
        content = data.get(page, {})
        if not content:
            continue
            
        cat = content.get("offensive_content_category")
        if cat and cat != "N/A":
            categories[page] = cat
            
        subcats = content.get("sub_categories", [])
        if subcats:
            subcategories[page] = subcats
    
    # Analyze how categories should be inherited
    category_inheritance = {}
    main_categories = {}  # subcat -> main_category
    
    # First, identify main categories from TOC pages
    toc_pages = [p for p in pages if "toc" in p.lower()]
    for page in toc_pages:
        if page in categories:
            main_cat = categories[page]
            # All subcategories from TOC should inherit this category
            if page in subcategories:
                for subcat in subcategories[page]:
                    main_categories[subcat] = main_cat
    
    # Now analyze each page for inheritance
    for page in pages:
        if page not in categories or categories[page] == "N/A":
            # Find the category this page should inherit
            inherited_cat = None
            
            # Check if any subcategories on this page have known main categories
            if page in subcategories:
                for subcat in subcategories[page]:
                    if subcat in main_categories:
                        inherited_cat = main_categories[subcat]
                        break
            
            # If still no category found, use the most recent previous category
            if not inherited_cat:
                prev_pages = [p for p in pages if p < page and p in categories and categories[p] != "N/A"]
                if prev_pages:
                    inherited_cat = categories[max(prev_pages)]
            
            if inherited_cat:
                category_inheritance[page] = inherited_cat
    
    return categories, category_inheritance, subcategories, main_categories

def generate_inheritance_report(data, categories, category_inheritance, subcategories, main_categories):
    """Generate a report showing how categories should be inherited."""
    pages = sorted(data.keys())
    report = []
    
    for page in pages:
        content = data.get(page, {})
        
        # Get actual and inherited categories
        actual_cat = categories.get(page, "N/A")
        inherited_cat = category_inheritance.get(page, "N/A") if actual_cat == "N/A" else actual_cat
        
        # Count entities
        page_subcats = subcategories.get(page, [])
        guidelines = content.get("guidelines", [])
        rules = content.get("rules", [])
        
        # Track inheritance issues
        has_inheritance_issue = actual_cat == "N/A" and inherited_cat != "N/A"
        
        # Classification
        classification = "REGULAR"
        if "TOC" in page.upper():
            classification = "FULL_TOC"
        elif "DETAILS" in page.upper():
            classification = "HYBRID"
        
        report.append({
            "Page": page,
            "Actual_Category": actual_cat,
            "Should_Inherit_From": inherited_cat,
            "Inheritance_Issue": "YES" if has_inheritance_issue else "NO",
            "Subcategories": len(page_subcats),
            "Guidelines": len(guidelines),
            "Rules": len(rules),
            "Classification": classification
        })
    
    return report

def categorize_subcategories(subcategories, main_categories):
    """Categorize subcategories by their main category."""
    categorized = {}
    
    for subcat, main_cat in main_categories.items():
        if main_cat not in categorized:
            categorized[main_cat] = []
        categorized[main_cat].append(subcat)
    
    # Add subcategories without a known main category
    uncategorized = []
    for page, subcats in subcategories.items():
        for subcat in subcats:
            if subcat not in main_categories:
                uncategorized.append((page, subcat))
    
    return categorized, uncategorized

def print_inheritance_report(report):
    """Print the inheritance report."""
    if not report:
        print("No data to report")
        return
        
    df = pd.DataFrame(report)
    
    # Calculate totals
    inheritance_issues = sum(1 for r in report if r["Inheritance_Issue"] == "YES")
    
    print("\n=== CATEGORY INHERITANCE REPORT ===")
    print(f"Pages with inheritance issues: {inheritance_issues} / {len(report)}")
    print(tabulate(df, headers='keys', tablefmt='grid'))

def print_subcategory_report(categorized, uncategorized):
    """Print report of categorized subcategories."""
    print("\n=== SUBCATEGORY CATEGORIZATION ===")
    
    if categorized:
        for main_cat, subcats in categorized.items():
            print(f"\nCategory: {main_cat} ({len(subcats)} subcategories)")
            for i, subcat in enumerate(sorted(subcats), 1):
                print(f"  {i}. {subcat}")
    else:
        print("No categorized subcategories found")
    
    if uncategorized:
        print(f"\nUncategorized Subcategories ({len(uncategorized)}):")
        for i, (page, subcat) in enumerate(sorted(uncategorized), 1):
            print(f"  {i}. {subcat} (from {page})")
    else:
        print("\nNo uncategorized subcategories found")

def visualize_inheritance(categories, category_inheritance, output_dir, output_file):
    """Create a visualization of category inheritance."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)
    
    # Create directed graph
    G = nx.DiGraph()
    
    # Add nodes for pages
    for page in set(categories.keys()) | set(category_inheritance.keys()):
        G.add_node(page, type="page")
    
    # Add nodes for categories and edges
    for page, cat in categories.items():
        if cat != "N/A":
            cat_node = f"Category: {cat}"
            G.add_node(cat_node, type="category")
            G.add_edge(cat_node, page, type="has_page", style="solid")
    
    # Add inheritance edges
    for page, cat in category_inheritance.items():
        if page not in categories or categories[page] == "N/A":
            cat_node = f"Category: {cat}"
            if cat_node not in G:
                G.add_node(cat_node, type="category")
            G.add_edge(cat_node, page, type="should_inherit", style="dashed")
    
    # Create the visualization
    plt.figure(figsize=(12, 10))
    
    # Define node positions using hierarchical layout
    pos = nx.spring_layout(G, seed=42)
    
    # Draw nodes with different colors
    category_nodes = [n for n in G.nodes() if G.nodes[n].get("type") == "category"]
    page_nodes = [n for n in G.nodes() if G.nodes[n].get("type") == "page"]
    
    nx.draw_networkx_nodes(G, pos, nodelist=category_nodes, node_color="skyblue", 
                           node_size=500, alpha=0.8, node_shape='o')
    nx.draw_networkx_nodes(G, pos, nodelist=page_nodes, node_color="lightgreen", 
                           node_size=300, alpha=0.8, node_shape='s')
    
    # Draw edges with different styles
    solid_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("style") == "solid"]
    dashed_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("style") == "dashed"]
    
    nx.draw_networkx_edges(G, pos, edgelist=solid_edges, alpha=0.7, arrows=True)
    nx.draw_networkx_edges(G, pos, edgelist=dashed_edges, alpha=0.5, arrows=True, 
                          style="dashed", edge_color="red")
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8)
    
    # Create legend
    plt.plot([0], [0], color='skyblue', marker='o', markersize=10, linestyle='', label='Category')
    plt.plot([0], [0], color='lightgreen', marker='s', markersize=10, linestyle='', label='Page')
    plt.plot([0], [0], color='black', markersize=0, linestyle='-', label='Has Category')
    plt.plot([0], [0], color='red', markersize=0, linestyle='--', label='Should Inherit')
    
    plt.legend(loc='upper right')
    plt.axis('off')
    plt.title('Category Inheritance Across Pages')
    plt.tight_layout()
    
    # Save the visualization
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nCategory inheritance visualization saved to: {output_path}")

def save_inheritance_data(report, categorized, uncategorized, output_dir, output_file):
    """Save inheritance data to file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)
    
    data = {
        "inheritance_report": report,
        "categorized_subcategories": {k: v for k, v in categorized.items()},
        "uncategorized_subcategories": [{"page": p, "subcategory": s} for p, s in uncategorized]
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Inheritance data saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Analyze category inheritance across pages')
    parser.add_argument('--pages', nargs='+', required=True, help='List of page names (e.g., page_1_toc page_1_details page_2)')
    parser.add_argument('--extracted-dir', default='extracted_entities', help='Directory containing extracted entity files')
    parser.add_argument('--output-dir', default='experimental/reporting/outputs', help='Directory to save reports')
    parser.add_argument('--data-file', default='inheritance_data.json', help='Filename for inheritance data')
    parser.add_argument('--viz-file', default='inheritance_graph.png', help='Filename for inheritance visualization')
    
    args = parser.parse_args()
    
    # Load extracted data
    data = load_extracted_data(args.extracted_dir, args.pages)
    
    # Analyze inheritance
    categories, category_inheritance, subcategories, main_categories = analyze_inheritance(data)
    
    # Generate report
    report = generate_inheritance_report(data, categories, category_inheritance, subcategories, main_categories)
    
    # Categorize subcategories
    categorized, uncategorized = categorize_subcategories(subcategories, main_categories)
    
    # Print reports
    print_inheritance_report(report)
    print_subcategory_report(categorized, uncategorized)
    
    # Visualize inheritance
    try:
        visualize_inheritance(categories, category_inheritance, args.output_dir, args.viz_file)
    except Exception as e:
        print(f"Error generating inheritance visualization: {e}")
    
    # Save data
    save_inheritance_data(report, categorized, uncategorized, args.output_dir, args.data_file)

if __name__ == "__main__":
    main()