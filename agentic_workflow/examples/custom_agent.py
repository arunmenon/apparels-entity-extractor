"""
Example demonstrating how to create and use a custom agent in the workflow.

This module shows how to:
1. Create a custom agent by inheriting from the base Agent class
2. Register the agent with the workflow
3. Run a workflow with the custom agent included
"""

import os
import sys
import json
from typing import Any, Dict, List

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agentic_workflow.agent_base import Agent
from agentic_workflow.workflow import AgenticWorkflow


class HallucinationDetectorAgent(Agent):
    """
    Custom agent that detects and flags potential hallucinations in entity extraction.
    
    This agent analyzes extracted entities and flags potentially hallucinated content
    by comparing against known patterns and reference data.
    """
    
    # Set agent type for factory registration
    agent_type = "hallucination_detector"
    
    def __init__(self, reference_file: str = None, name: str = None):
        """
        Initialize the hallucination detector with optional reference data.
        
        Args:
            reference_file: Path to reference data file
            name: Optional agent name
        """
        super().__init__(name or "HallucinationDetector")
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
    
    def pre_process(self, data: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Ensure we have the extracted data to check."""
        if 'extracted_data' not in data:
            print(f"No extracted data found for page {data.get('page_num', 'unknown')}")
    
    def execute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for hallucinations in the extracted data.
        
        Args:
            data: Input data with extraction results
            context: Shared workflow context
            
        Returns:
            Dictionary with hallucination detection results
        """
        if 'extracted_data' not in data:
            return {'hallucination_issues': []}
        
        page_num = data.get('page_num', 0)
        extracted_data = data['extracted_data']
        
        # Update stats
        self.hallucination_stats["pages_checked"] += 1
        
        # Check for hallucinations
        issues = []
        
        # 1. Check primary category
        category = extracted_data.get("offensive_content_category", "")
        if category:
            # Track categories we've seen
            if category not in self.hallucination_stats["categories"]:
                self.hallucination_stats["categories"][category] = 0
            self.hallucination_stats["categories"][category] += 1
            
            # Check if this doesn't match our known primary category
            if (self.reference_data.get("primary_category") and 
                category != self.reference_data.get("primary_category")):
                issues.append({
                    "type": "hallucinated_category",
                    "message": f"Potential hallucinated category: '{category}' " + 
                              f"(expected: '{self.reference_data.get('primary_category')}')"
                })
        
        # 2. Check subcategories
        subcategories = extracted_data.get("sub_categories", [])
        valid_subcategories = self.reference_data.get("valid_subcategories", [])
        
        for subcategory in subcategories:
            # Normalize subcategory format
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
                if valid_subcategories and subcat_name not in valid_subcategories:
                    issues.append({
                        "type": "hallucinated_subcategory",
                        "message": f"Potential hallucinated subcategory: '{subcat_name}'"
                    })
        
        # Update hallucination stats
        if issues:
            self.hallucination_stats["potential_hallucinations"] += len(issues)
        
        # Return the hallucination detection results
        return {
            'hallucination_issues': issues,
            'hallucination_stats': self.hallucination_stats
        }
    
    def post_process(self, result: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Log any hallucination issues found."""
        issues = result.get('hallucination_issues', [])
        page_num = result.get('page_num', 'unknown')
        
        if issues:
            print(f"\nPotential hallucinations on page {page_num}:")
            for issue in issues:
                print(f"  - {issue['message']}")


def main():
    """Run a workflow with the custom hallucination detector agent."""
    # Create the workflow
    workflow = AgenticWorkflow()
    
    # Create and register the hallucination detector agent
    hallucination_detector = HallucinationDetectorAgent(
        reference_file="ground_truth_subcategories.json"
    )
    
    # Register the agent at the end of the pipeline
    workflow.register_agent("hallucination_detector", hallucination_detector)
    
    # Run the workflow with a small page limit for demonstration
    print("Running workflow with hallucination detection...")
    workflow.process_images(limit=2, sequential=True)
    
    # Generate and save a hallucination report
    stats = hallucination_detector.hallucination_stats
    
    print("\n--- Hallucination Detection Report ---")
    print(f"Pages checked: {stats['pages_checked']}")
    print(f"Potential hallucinations: {stats['potential_hallucinations']}")
    
    # Save report to file
    with open("hallucination_report.json", "w") as f:
        # Convert categories and subcategories from dict to list for better serialization
        report = stats.copy()
        report["categories"] = list(stats["categories"].keys())
        report["subcategories"] = list(stats["subcategories"].keys())
        json.dump(report, f, indent=4)
    
    print("Detailed hallucination report saved to hallucination_report.json")


if __name__ == "__main__":
    main()