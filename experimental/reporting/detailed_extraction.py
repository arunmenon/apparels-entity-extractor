#!/usr/bin/env python3
"""
Script to generate detailed extraction reports for regular pages, showing all content.
"""

import os
import json
import argparse
from pathlib import Path
import pandas as pd
from tabulate import tabulate

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

def extract_page_details(data):
    """Extract detailed content for each page."""
    details = {}
    
    for page, content in data.items():
        if not content:
            details[page] = {
                "category": "N/A",
                "subcategories": [],
                "guidelines": [],
                "rules": []
            }
            continue
        
        # Classification
        classification = "REGULAR"
        if "TOC" in page.upper():
            classification = "FULL_TOC"
        elif "DETAILS" in page.upper():
            classification = "HYBRID"
        
        category = content.get("offensive_content_category", "N/A")
        subcategories = content.get("sub_categories", [])
        
        # Extract guidelines
        guidelines = []
        for guideline in content.get("guidelines", []):
            if "description" in guideline:
                guidelines.append(guideline["description"])
            else:
                guidelines.append(str(guideline))
        
        # Extract rules
        rules = []
        for rule in content.get("rules", []):
            rule_type = rule.get("type", "unknown")
            status = rule.get("status", "unknown")
            description = rule.get("description", "No description")
            rules.append({
                "type": rule_type,
                "status": status,
                "description": description
            })
        
        details[page] = {
            "category": category,
            "classification": classification,
            "subcategories": subcategories,
            "guidelines": guidelines,
            "rules": rules
        }
    
    return details

def print_detailed_extraction(details):
    """Print detailed extraction report for each page."""
    print("\n=== DETAILED EXTRACTION CONTENT ===\n")
    
    for page, content in sorted(details.items()):
        page_type = content.get("classification", "REGULAR")
        category = content.get("category", "N/A")
        
        print(f"\n{'='*20} PAGE: {page} ({'TOC' if page_type == 'FULL_TOC' else 'HYBRID' if page_type == 'HYBRID' else 'REGULAR'}) {'='*20}")
        print(f"Category: {category}")
        
        # Print subcategories
        subcats = content.get("subcategories", [])
        print(f"\nSUBCATEGORIES ({len(subcats)}):")
        if subcats:
            for i, subcat in enumerate(subcats, 1):
                print(f"  {i}. {subcat}")
        else:
            print("  None found")
        
        # Print guidelines
        guidelines = content.get("guidelines", [])
        print(f"\nGUIDELINES ({len(guidelines)}):")
        if guidelines:
            for i, guideline in enumerate(guidelines, 1):
                print(f"  {i}. {guideline}")
        else:
            print("  None found")
        
        # Print rules
        rules = content.get("rules", [])
        print(f"\nRULES ({len(rules)}):")
        if rules:
            for i, rule in enumerate(rules, 1):
                rule_type = rule.get("type", "unknown")
                status = rule.get("status", "unknown")
                description = rule.get("description", "No description")
                print(f"  {i}. [{rule_type}] {description} ({status})")
        else:
            print("  None found")
        
        print("\n" + "-"*60)

def generate_summary_table(details):
    """Generate summary table of extracted content."""
    summary = []
    
    for page, content in sorted(details.items()):
        page_type = content.get("classification", "REGULAR")
        category = content.get("category", "N/A")
        subcats = len(content.get("subcategories", []))
        guidelines = len(content.get("guidelines", []))
        rules = len(content.get("rules", []))
        
        # Count rule types
        rule_types = {}
        for rule in content.get("rules", []):
            rule_type = rule.get("type", "unknown")
            if rule_type not in rule_types:
                rule_types[rule_type] = 0
            rule_types[rule_type] += 1
        
        # Count rule statuses
        rule_statuses = {}
        for rule in content.get("rules", []):
            status = rule.get("status", "unknown")
            if status not in rule_statuses:
                rule_statuses[status] = 0
            rule_statuses[status] += 1
        
        summary.append({
            "Page": page,
            "Type": page_type,
            "Category": category,
            "Subcategories": subcats,
            "Guidelines": guidelines,
            "Rules": rules,
            "Rule_Types": rule_types,
            "Rule_Statuses": rule_statuses
        })
    
    return summary

def print_summary_table(summary):
    """Print summary table of extracted content."""
    # Create DataFrame for basic summary
    df = pd.DataFrame([{
        "Page": item["Page"],
        "Type": item["Type"],
        "Category": item["Category"],
        "Subcategories": item["Subcategories"],
        "Guidelines": item["Guidelines"],
        "Rules": item["Rules"]
    } for item in summary])
    
    print("\n=== EXTRACTION SUMMARY ===")
    print(tabulate(df, headers='keys', tablefmt='grid'))
    
    # Calculate totals
    total_subcats = sum(item["Subcategories"] for item in summary)
    total_guidelines = sum(item["Guidelines"] for item in summary)
    total_rules = sum(item["Rules"] for item in summary)
    
    # Calculate rule type counts
    rule_types = {}
    for item in summary:
        for rule_type, count in item["Rule_Types"].items():
            if rule_type not in rule_types:
                rule_types[rule_type] = 0
            rule_types[rule_type] += count
    
    # Calculate rule status counts
    rule_statuses = {}
    for item in summary:
        for status, count in item["Rule_Statuses"].items():
            if status not in rule_statuses:
                rule_statuses[status] = 0
            rule_statuses[status] += count
    
    print(f"\nTOTALS:")
    print(f"  Total Pages: {len(summary)}")
    print(f"  Total Subcategories: {total_subcats}")
    print(f"  Total Guidelines: {total_guidelines}")
    print(f"  Total Rules: {total_rules}")
    
    print("\nRULE TYPES:")
    for rule_type, count in rule_types.items():
        print(f"  {rule_type}: {count}")
    
    print("\nRULE STATUSES:")
    for status, count in rule_statuses.items():
        print(f"  {status}: {count}")

def save_detailed_extraction(details, summary, output_dir, output_file):
    """Save detailed extraction data to file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)
    
    data = {
        "details": details,
        "summary": summary
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nDetailed extraction data saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Generate detailed extraction reports for pages')
    parser.add_argument('--pages', nargs='+', required=True, help='List of page names (e.g., page_1_toc page_1_details page_2)')
    parser.add_argument('--extracted-dir', default='extracted_entities', help='Directory containing extracted entity files')
    parser.add_argument('--output-dir', default='experimental/reporting/outputs', help='Directory to save reports')
    parser.add_argument('--output-file', default='detailed_extraction.json', help='Filename for detailed extraction data')
    parser.add_argument('--regular-only', action='store_true', help='Only show detailed extraction for regular pages')
    
    args = parser.parse_args()
    
    # Load extracted data
    data = load_extracted_data(args.extracted_dir, args.pages)
    
    # Extract page details
    details = extract_page_details(data)
    
    # Filter to regular pages if requested
    if args.regular_only:
        details = {page: content for page, content in details.items() 
                   if content.get("classification") == "REGULAR"}
    
    # Generate summary
    summary = generate_summary_table(details)
    
    # Print reports
    print_summary_table(summary)
    print_detailed_extraction(details)
    
    # Save detailed extraction
    save_detailed_extraction(details, summary, args.output_dir, args.output_file)

if __name__ == "__main__":
    main()