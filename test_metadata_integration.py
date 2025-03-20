#!/usr/bin/env python3
"""
Test script to verify that the relationship property metadata is correctly integrated into the schema.
This script refreshes the schema, validates that property metadata is included, and checks
that the schema includes the MAY_VIOLATE confidence thresholds.
"""

import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the schema manager
from agentic_workflow.graph_rag.schema.schema_manager import schema_manager

def check_metadata_integration():
    """Verify that the relationship metadata is correctly integrated into the schema."""
    
    # Force a refresh of the schema
    logger.info("Forcing refresh of the schema...")
    formatted_schema = schema_manager.get_formatted_schema(force_refresh=True)
    formatted_rich_context = schema_manager.get_formatted_rich_context(force_refresh=True)
    
    # Check if the schema includes property metadata
    logger.info("Checking if schema includes confidence measures...")
    has_confidence_measures = "Relationships with Confidence Measures" in formatted_schema
    
    # Check if the rich context includes property metadata
    logger.info("Checking if rich context includes property information...")
    has_property_info = "Relationship Property Information" in formatted_rich_context
    
    # Check specifically for MAY_VIOLATE relationship with threshold
    logger.info("Checking for MAY_VIOLATE confidence threshold...")
    has_may_violate = "MAY_VIOLATE" in formatted_schema and "confidence_score" in formatted_schema
    
    # Print the results
    logger.info(f"Has confidence measures in schema: {has_confidence_measures}")
    logger.info(f"Has property information in rich context: {has_property_info}")
    logger.info(f"Has MAY_VIOLATE confidence threshold: {has_may_violate}")
    
    # Save the output to a file for inspection
    with open("schema_with_metadata.txt", "w") as f:
        f.write(formatted_schema)
    
    with open("rich_context_with_metadata.txt", "w") as f:
        f.write(formatted_rich_context)
    
    logger.info("Saved schema and rich context to files for inspection")
    
    # Return True if everything is working correctly
    return has_confidence_measures and has_property_info and has_may_violate

if __name__ == "__main__":
    success = check_metadata_integration()
    logger.info(f"Integration test {'SUCCESS' if success else 'FAILED'}")