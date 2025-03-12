"""
Statistics collection hooks for entity extraction workflows.

This module provides observers for gathering statistics about the workflow.
"""

import os
import json
import time
from typing import Any, Dict, List, Set, Optional

from ..agent_base import Observer, Subject


class StatisticsObserver(Observer):
    """
    Observer that collects statistics about the workflow.
    
    This observer tracks metrics like page types, entity counts,
    processing times, and overall workflow performance.
    """
    
    def __init__(self, output_file: str = "workflow_statistics.json"):
        """
        Initialize the statistics observer.
        
        Args:
            output_file: File to save the statistics
        """
        self.output_file = output_file
        self.stats = {
            'start_time': time.time(),
            'page_types': {
                'FULL_TOC': 0,
                'HYBRID': 0,
                'REGULAR': 0,
                'UNKNOWN': 0
            },
            'entity_counts': {
                'subcategories': set(),
                'guidelines': 0,
                'rules': {
                    'policy_rule': 0,
                    'imperium_rule': 0,
                    'image_detection_rule': 0
                }
            },
            'processing_times': {
                'classification': 0,
                'extraction': 0,
                'context': 0,
                'cypher': 0
            }
        }
    
    def update(self, subject: Subject, event_type: str, data: Any) -> None:
        """
        Receive update from a subject.
        
        Args:
            subject: The subject sending the notification
            event_type: The type of event that occurred
            data: Any relevant data for the event
        """
        if event_type == "post_classify" and isinstance(data, dict):
            # Track page type
            page_type = data.get('classification', 'UNKNOWN')
            self.stats['page_types'][page_type] = self.stats['page_types'].get(page_type, 0) + 1
            
            # Track classification time
            if 'classify_time' in data:
                self.stats['processing_times']['classification'] += data['classify_time']
        
        elif event_type == "post_extract" and isinstance(data, dict):
            # Track extraction time
            if 'extract_time' in data:
                self.stats['processing_times']['extraction'] += data['extract_time']
            
            # Track entity counts from extracted data
            if 'extracted_data' in data:
                extracted = data['extracted_data']
                
                # Track subcategories
                for subcat in extracted.get('sub_categories', []):
                    if isinstance(subcat, dict) and 'name' in subcat:
                        self.stats['entity_counts']['subcategories'].add(subcat['name'])
                    else:
                        self.stats['entity_counts']['subcategories'].add(subcat)
                
                # Track guidelines
                self.stats['entity_counts']['guidelines'] += len(extracted.get('guidelines', []))
                
                # Track rules by type
                for rule in extracted.get('rules', []):
                    rule_type = rule.get('type', 'unknown')
                    self.stats['entity_counts']['rules'][rule_type] = self.stats['entity_counts']['rules'].get(rule_type, 0) + 1
        
        elif event_type == "post_context" and isinstance(data, dict):
            # Track context time
            if 'context_time' in data:
                self.stats['processing_times']['context'] += data['context_time']
        
        elif event_type == "post_cypher" and isinstance(data, dict):
            # Track cypher time
            if 'cypher_time' in data:
                self.stats['processing_times']['cypher'] += data['cypher_time']
        
        elif event_type == "workflow_end" and isinstance(data, dict):
            # Calculate final statistics
            self._calculate_final_stats(data)
            
            # Save statistics
            self._save_statistics()
            
            # Print summary
            self._print_summary()
    
    def _calculate_final_stats(self, final_results: Dict[str, Any]) -> None:
        """
        Calculate final statistics at the end of the workflow.
        
        Args:
            final_results: The final workflow results
        """
        # Calculate total execution time
        self.stats['execution_time'] = time.time() - self.stats['start_time']
        
        # Calculate total pages
        self.stats['total_pages'] = len(final_results.get('page_results', {}))
        
        # Convert set to list for JSON serialization
        self.stats['entity_counts']['subcategories'] = list(self.stats['entity_counts']['subcategories'])
        self.stats['entity_counts']['total_subcategories'] = len(self.stats['entity_counts']['subcategories'])
        
        # Calculate total rules
        self.stats['entity_counts']['total_rules'] = sum(self.stats['entity_counts']['rules'].values())
        
        # Average processing times per page
        if self.stats['total_pages'] > 0:
            for key in self.stats['processing_times']:
                self.stats['processing_times'][f'avg_{key}'] = self.stats['processing_times'][key] / self.stats['total_pages']
    
    def _save_statistics(self) -> None:
        """Save the collected statistics to a file."""
        with open(self.output_file, "w") as f:
            json.dump(self.stats, f, indent=4)
    
    def _print_summary(self) -> None:
        """Print a summary of the statistics."""
        print("\nWorkflow Statistics:")
        print(f"- Total pages processed: {self.stats['total_pages']}")
        print(f"- Page types: TOC: {self.stats['page_types']['FULL_TOC']}, " + 
              f"Hybrid: {self.stats['page_types']['HYBRID']}, " + 
              f"Regular: {self.stats['page_types']['REGULAR']}")
        print(f"- Total unique subcategories: {self.stats['entity_counts']['total_subcategories']}")
        print(f"- Total rules: {self.stats['entity_counts']['total_rules']}")
        print(f"- Total execution time: {self.stats['execution_time']:.2f}s")
        print(f"- Statistics saved to: {self.output_file}")