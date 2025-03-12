"""
Validation hooks for entity extraction workflows.

This module provides observers for validating entity extraction results.
"""

import os
import json
from typing import Any, Dict, List, Set, Optional

from ..agent_base import Observer, Subject


class ValidationObserver(Observer):
    """
    Observer that validates extraction results for quality.
    
    This observer checks for potential issues like hallucinations,
    missing data, or inconsistencies in the extracted entities.
    """
    
    def __init__(self, log_dir: str = "failed_queries"):
        """
        Initialize the validation observer.
        
        Args:
            log_dir: Directory to save validation issues
        """
        self.log_dir = log_dir
        self.validation_stats = {
            "pages_validated": 0,
            "issues_found": 0,
            "issue_types": {}
        }
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
    
    def update(self, subject: Subject, event_type: str, data: Any) -> None:
        """
        Receive update from a subject.
        
        Args:
            subject: The subject sending the notification
            event_type: The type of event that occurred
            data: Any relevant data for the event
        """
        # Only validate post_extract events
        if event_type != "post_extract" or not isinstance(data, dict):
            return
        
        if 'extracted_data' not in data:
            return
        
        page_num = data.get('page_num', 'unknown')
        self.validation_stats["pages_validated"] += 1
        
        # Validate the extracted data
        issues = self._validate_extracted_data(data)
        
        # Log any issues found
        if issues:
            self.validation_stats["issues_found"] += len(issues)
            
            # Track issue types
            for issue in issues:
                issue_type = issue.get("type", "unknown")
                self.validation_stats["issue_types"][issue_type] = self.validation_stats["issue_types"].get(issue_type, 0) + 1
            
            # Log to console
            print(f"\nVALIDATION ISSUES for page {page_num}:")
            for issue in issues:
                print(f"  - {issue['message']}")
            
            # Save issue log
            log_file = os.path.join(self.log_dir, f"validation_issues_page_{page_num}.json")
            with open(log_file, "w") as f:
                json.dump({
                    "page": page_num,
                    "issues": issues,
                    "data": data.get('extracted_data')
                }, f, indent=4)
            
            # Add issues to the data for downstream use
            data["validation_issues"] = issues
    
    def _validate_extracted_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate extracted data for quality and correctness.
        
        Args:
            data: Page data with extracted entities
            
        Returns:
            List of validation issues found
        """
        issues = []
        extracted_data = data.get('extracted_data', {})
        page_type = data.get('classification', 'UNKNOWN')
        
        # Check for missing primary category
        if not extracted_data.get('offensive_content_category'):
            issues.append({
                "type": "missing_category",
                "message": f"Missing primary category"
            })
        
        # Check for TOC pages with no subcategories
        if page_type in ['FULL_TOC', 'HYBRID'] and not extracted_data.get('sub_categories'):
            issues.append({
                "type": "missing_subcategories",
                "message": f"TOC page with no subcategories detected"
            })
        
        # Check for guidelines without parent subcategories
        guidelines = extracted_data.get('guidelines', [])
        subcategories = extracted_data.get('sub_categories', [])
        if guidelines and not subcategories:
            issues.append({
                "type": "orphaned_guidelines",
                "message": f"Guidelines without parent subcategories"
            })
        
        # Check for rules without guidelines
        rules = extracted_data.get('rules', [])
        if rules and not guidelines:
            issues.append({
                "type": "orphaned_rules",
                "message": f"Rules without parent guidelines"
            })
        
        return issues