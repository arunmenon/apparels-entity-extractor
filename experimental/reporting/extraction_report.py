#!/usr/bin/env python3
"""
A script to generate extraction reports for specified pages.
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

def generate_report(data):
    """Generate a report from the extracted data."""
    report = []
    
    for page, content in data.items():
        if not content:
            report.append({
                "Page": page,
                "Category": "N/A",
                "Subcategories": 0,
                "Guidelines": 0,
                "Rules": 0,
                "Classification": "Unknown"
            })
            continue
            
        category = content.get("offensive_content_category", "N/A")
        subcategories = content.get("sub_categories", [])
        guidelines = content.get("guidelines", [])
        rules = content.get("rules", [])
        
        # Determine page classification
        classification = "REGULAR"
        if "TOC" in page.upper():
            classification = "FULL_TOC"
        elif "DETAILS" in page.upper():
            classification = "HYBRID"
            
        report.append({
            "Page": page,
            "Category": category,
            "Subcategories": len(subcategories),
            "Guidelines": len(guidelines),
            "Rules": len(rules),
            "Classification": classification
        })
    
    return report

def detailed_report(data):
    """Generate detailed content reports."""
    detailed = {}
    
    for page, content in data.items():
        if not content:
            detailed[page] = {"error": "No content found"}
            continue
            
        # Extract entities from the page
        subcategories = content.get("sub_categories", [])
        guidelines = [g.get("description", "No description") for g in content.get("guidelines", [])]
        rules = []
        
        for rule in content.get("rules", []):
            rule_type = rule.get("type", "unknown")
            status = rule.get("status", "unknown")
            description = rule.get("description", "No description")
            rules.append(f"{rule_type} ({status}): {description}")
        
        detailed[page] = {
            "subcategories": subcategories,
            "guidelines": guidelines,
            "rules": rules
        }
    
    return detailed

def print_summary_report(report):
    """Print a summary report as a table."""
    if not report:
        print("No data to report")
        return
        
    df = pd.DataFrame(report)
    print("\n=== EXTRACTION SUMMARY REPORT ===")
    print(tabulate(df, headers='keys', tablefmt='grid'))
    
    # Print totals
    total_subcats = sum(item["Subcategories"] for item in report)
    total_guidelines = sum(item["Guidelines"] for item in report)
    total_rules = sum(item["Rules"] for item in report)
    
    print(f"\nTOTALS:")
    print(f"Total Pages: {len(report)}")
    print(f"Total Subcategories: {total_subcats}")
    print(f"Total Guidelines: {total_guidelines}")
    print(f"Total Rules: {total_rules}")

def print_detailed_report(detailed):
    """Print a detailed report for each page."""
    print("\n=== DETAILED EXTRACTION REPORT ===\n")
    
    for page, content in detailed.items():
        print(f"\n{'-'*20} PAGE: {page} {'-'*20}")
        
        if "error" in content:
            print(f"ERROR: {content['error']}")
            continue
            
        print("\nSUBCATEGORIES:")
        if content["subcategories"]:
            for i, subcat in enumerate(content["subcategories"], 1):
                print(f"{i}. {subcat}")
        else:
            print("None found")
            
        print("\nGUIDELINES:")
        if content["guidelines"]:
            for i, guideline in enumerate(content["guidelines"], 1):
                print(f"{i}. {guideline}")
        else:
            print("None found")
            
        print("\nRULES:")
        if content["rules"]:
            for i, rule in enumerate(content["rules"], 1):
                print(f"{i}. {rule}")
        else:
            print("None found")

def save_report(report, detailed, output_dir, summary_file, detailed_file):
    """Save reports to files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Save summary report
    df = pd.DataFrame(report)
    summary_path = os.path.join(output_dir, summary_file)
    df.to_csv(summary_path, index=False)
    
    # Save detailed report
    detailed_path = os.path.join(output_dir, detailed_file)
    with open(detailed_path, 'w') as f:
        json.dump(detailed, f, indent=2)
    
    print(f"\nReports saved to:")
    print(f"Summary: {summary_path}")
    print(f"Detailed: {detailed_path}")

def main():
    parser = argparse.ArgumentParser(description='Generate extraction reports for specified pages')
    parser.add_argument('--pages', nargs='+', required=True, help='List of page names (e.g., page_1_toc page_1_details page_2)')
    parser.add_argument('--extracted-dir', default='extracted_entities', help='Directory containing extracted entity files')
    parser.add_argument('--output-dir', default='experimental/reporting/outputs', help='Directory to save reports')
    parser.add_argument('--summary-file', default='extraction_summary.csv', help='Filename for summary report')
    parser.add_argument('--detailed-file', default='extraction_detailed.json', help='Filename for detailed report')
    
    args = parser.parse_args()
    
    # Load extracted data
    data = load_extracted_data(args.extracted_dir, args.pages)
    
    # Generate reports
    report = generate_report(data)
    detailed = detailed_report(data)
    
    # Print reports
    print_summary_report(report)
    print_detailed_report(detailed)
    
    # Save reports
    save_report(report, detailed, args.output_dir, args.summary_file, args.detailed_file)

if __name__ == "__main__":
    main()