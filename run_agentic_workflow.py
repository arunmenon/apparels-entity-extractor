#!/usr/bin/env python3
"""
Example script demonstrating how to use the agentic workflow.

This script provides a command-line interface for running the
entity extraction workflow with various options.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional

from agentic_workflow.workflow import AgenticWorkflow
from agentic_workflow.hooks import ValidationObserver, StatisticsObserver


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run the agentic workflow for entity extraction')
    
    # Basic options
    parser.add_argument('--limit', type=int, default=-1, 
                        help='Limit the number of pages to process')
    parser.add_argument('--sequential', action='store_true', 
                        help='Process pages sequentially instead of in parallel')
    parser.add_argument('--config', type=str, default='config.json', 
                        help='Path to config file')
    
    # Directory options
    parser.add_argument('--images-dir', type=str, default=None,
                        help='Directory containing page images')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory for output files')
    
    # Feature toggles
    parser.add_argument('--validate', action='store_true',
                        help='Enable validation hooks')
    parser.add_argument('--stats', action='store_true',
                        help='Generate workflow statistics')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--use-docling', action='store_true',
                        help='Use Docling for document processing and entity extraction')
    
    # Advanced options
    parser.add_argument('--save-context', action='store_true',
                        help='Save context after each page')
    parser.add_argument('--toc-page', type=int, default=0,
                        help='Index of TOC page (default is first page)')
    
    return parser.parse_args()


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('workflow.log'),
            logging.StreamHandler()
        ]
    )


def create_custom_observers(args) -> Dict[str, Any]:
    """Create custom observers based on command line arguments."""
    observers = {}
    
    if args.validate:
        observers['validation'] = ValidationObserver()
    
    if args.stats:
        observers['statistics'] = StatisticsObserver()
    
    return observers


def main() -> int:
    """Main entry point for the workflow."""
    args = parse_arguments()
    
    # Set up logging
    setup_logging(args.debug)
    
    print("Initializing agentic workflow...")
    
    try:
        # Load the configuration
        import json
        with open(args.config, "r") as config_file:
            config = json.load(config_file)
            
        # Override config values based on arguments
        if args.use_docling:
            config["use_docling"] = True
            config["entity_extractor"]["type"] = "docling"
            print("Using Docling for document processing and entity extraction")
            
        # Write the updated config back to a temporary file
        temp_config_path = "temp_config.json"
        with open(temp_config_path, "w") as temp_config_file:
            json.dump(config, temp_config_file, indent=2)
            
        # Create the workflow with updated config
        workflow = AgenticWorkflow(config_path=temp_config_path)
        
        # Override directories if specified
        if args.images_dir:
            workflow.images_dir = args.images_dir
            print(f"Using custom images directory: {workflow.images_dir}")
        
        if args.output_dir:
            workflow.extracted_dir = os.path.join(args.output_dir, "extracted_entities")
            workflow.incremental_dir = os.path.join(args.output_dir, "incremental_cypher")
            os.makedirs(workflow.extracted_dir, exist_ok=True)
            os.makedirs(workflow.incremental_dir, exist_ok=True)
            print(f"Using custom output directory: {args.output_dir}")
        
        # Apply TOC page configuration
        if args.toc_page != 0:
            workflow.context.set_state("toc_page_index", args.toc_page)
            print(f"Using page {args.toc_page} as TOC page")
        
        # Register custom observers
        observers = create_custom_observers(args)
        for event_type, observer in observers.items():
            workflow.register_observer(observer, event_type)
            print(f"Registered {event_type} observer")
        
        # Process images
        print(f"Processing images from: {workflow.images_dir}")
        print(f"Mode: {'Sequential' if args.sequential else 'Parallel'}")
        if args.limit > 0:
            print(f"Limited to {args.limit} pages")
        
        # Run the workflow
        results = workflow.process_images(
            limit=args.limit if args.limit > 0 else None,
            sequential=args.sequential
        )
        
        print("\nWorkflow completed successfully!")
        print(f"- Extracted entities saved to: {workflow.extracted_dir}")
        print(f"- Incremental Cypher queries saved to: {workflow.incremental_dir}")
        print("- Final Cypher query saved to: final_cypher.json")
        
        return 0
        
    except Exception as e:
        logging.exception(f"Error during workflow execution: {str(e)}")
        print(f"Error during workflow execution: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())