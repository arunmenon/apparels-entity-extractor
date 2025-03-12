#!/usr/bin/env python3
"""
Example demonstrating how to create and register a custom agent in the workflow.
"""

import os
import sys
import json

# Add parent directory to path so we can import the agentic_workflow module
sys.path.append('/Users/arunmenon/projects/apparels-entity-extractor')
from agentic_workflow.agent_workflow import AgentWorkflow

class HallucinationDetectorAgent:
    """
    Custom agent that detects and flags potential hallucinations in entity extraction.
    
    This agent analyzes extracted entities and flags potentially hallucinated content
    by comparing against known patterns and reference data.
    """
    
    def __init__(self, reference_file=None):
        """Initialize the hallucination detector with optional reference data."""
        self.reference_data = {}
        self.hallucination_stats = {
            "pages_checked": 0,
            "potential_hallucinations": 0,
            "categories": {},
            "subcategories": {}
        }
        
        # Load reference data if provided
        if reference_file and os.path.exists(reference_file):
            try:
                with open(reference_file, 'r') as f:
                    self.reference_data = json.load(f)
                print(f"Loaded reference data from {reference_file}")
            except Exception as e:
                print(f"Error loading reference data: {e}")
    
    def check_for_hallucinations(self, extracted_data, page_num):
        """
        Check extracted data for potential hallucinations.
        
        Args:
            extracted_data: The structured data from entity extraction
            page_num: Page number for reference
            
        Returns:
            List of potential hallucination issues
        """
        self.hallucination_stats["pages_checked"] += 1
        issues = []
        
        # Check primary category
        category = extracted_data.get("offensive_content_category", "")
        if category:
            # Track categories we've seen
            if category not in self.hallucination_stats["categories"]:
                self.hallucination_stats["categories"][category] = 0
            self.hallucination_stats["categories"][category] += 1
            
            # Check if this doesn't match our known primary category
            if self.reference_data.get("primary_category") and category != self.reference_data.get("primary_category"):
                issues.append(f"Potential hallucinated category: '{category}' (expected: '{self.reference_data.get('primary_category')}')")
        
        # Check subcategories
        subcategories = extracted_data.get("sub_categories", [])
        for subcategory in subcategories:
            if isinstance(subcategory, dict):
                subcat_name = subcategory.get("name", "")
            else:
                subcat_name = subcategory
                
            if subcat_name:
                # Track subcategories we've seen
                if subcat_name not in self.hallucination_stats["subcategories"]:
                    self.hallucination_stats["subcategories"][subcat_name] = 0
                self.hallucination_stats["subcategories"][subcat_name] += 1
                
                # Check against reference subcategories if available
                if self.reference_data.get("valid_subcategories") and subcat_name not in self.reference_data.get("valid_subcategories", []):
                    issues.append(f"Potential hallucinated subcategory: '{subcat_name}'")
        
        # Update hallucination stats
        if issues:
            self.hallucination_stats["potential_hallucinations"] += len(issues)
        
        return issues
    
    def get_statistics(self):
        """Return statistics on hallucination detection."""
        return self.hallucination_stats

# Hook function to analyze extracted data for hallucinations
def hallucination_detection_hook(workflow, page_data, **kwargs):
    """Hook to check for hallucinations after entity extraction."""
    # Initialize the detector if not already present
    if not hasattr(workflow, "hallucination_detector"):
        workflow.hallucination_detector = HallucinationDetectorAgent(
            reference_file="ground_truth_subcategories.json"
        )
    
    # Check for hallucinations if we have extracted data
    if "extracted_data" in page_data:
        page_num = page_data.get("page_num", 0)
        issues = workflow.hallucination_detector.check_for_hallucinations(
            page_data["extracted_data"], page_num
        )
        
        # Log any issues found
        if issues:
            print(f"\nPotential hallucinations on page {page_num}:")
            for issue in issues:
                print(f"  - {issue}")
            
            # Add hallucination info to page data for downstream use
            page_data["hallucination_issues"] = issues

# Hook to generate a final hallucination report
def generate_hallucination_report(workflow, final_results, **kwargs):
    """Generate a final report on hallucinations detected across all pages."""
    if hasattr(workflow, "hallucination_detector"):
        stats = workflow.hallucination_detector.get_statistics()
        
        # Generate report
        print("\n--- Hallucination Detection Report ---")
        print(f"Pages checked: {stats['pages_checked']}")
        print(f"Potential hallucinations: {stats['potential_hallucinations']}")
        
        # Save report to file
        with open("hallucination_report.json", "w") as f:
            json.dump(stats, f, indent=4)
        
        print("Detailed hallucination report saved to hallucination_report.json")

def main():
    """Run the workflow with hallucination detection."""
    # Initialize workflow
    workflow = AgentWorkflow()
    
    # Register hooks
    workflow.register_hook("post_extract", hallucination_detection_hook)
    workflow.register_hook("post_process", generate_hallucination_report)
    
    # Process just 1 page for quick demonstration
    workflow.process_images_sequential(limit=1)

if __name__ == "__main__":
    main()