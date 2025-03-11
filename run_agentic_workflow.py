#!/usr/bin/env python3
"""
Example script demonstrating how to use the agentic workflow.
"""

import os
import sys
import argparse
from agentic_workflow import AgentWorkflow

def main():
    parser = argparse.ArgumentParser(description='Run the agentic workflow for compliance document processing')
    parser.add_argument('--limit', type=int, default=-1, help='Limit the number of pages to process')
    parser.add_argument('--sequential', action='store_true', help='Process pages sequentially instead of in parallel')
    parser.add_argument('--config', type=str, default='config.json', help='Path to config file')
    parser.add_argument('--images-dir', type=str, default='output_images', help='Directory containing page images')
    
    args = parser.parse_args()
    
    print("Initializing agentic workflow...")
    workflow = AgentWorkflow(config_path=args.config)
    
    # Override images directory if specified
    if args.images_dir != 'output_images':
        workflow.images_dir = args.images_dir
    
    print(f"Processing images from: {workflow.images_dir}")
    print(f"Mode: {'Sequential' if args.sequential else 'Parallel'}")
    if args.limit > 0:
        print(f"Limited to {args.limit} pages")
    
    # Process images based on arguments
    try:
        if args.sequential:
            workflow.process_images_sequential(limit=args.limit if args.limit > 0 else None)
        else:
            workflow.process_images_parallel(limit=args.limit if args.limit > 0 else None)
        
        print("Workflow completed successfully!")
        print(f"- Extracted entities saved to: {workflow.extracted_dir}")
        print(f"- Incremental Cypher queries saved to: {workflow.incremental_dir}")
        print("- Final Cypher query saved to: final_cypher.json")
        print("- Context data saved to: compliance_context.json")
        
    except Exception as e:
        print(f"Error during workflow execution: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())