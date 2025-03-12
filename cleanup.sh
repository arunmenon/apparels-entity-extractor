#!/bin/bash
# Cleanup script to remove unnecessary files from root folder

# Remove the duplicate context extractor (now integrated in agentic_workflow)
rm -f context_enhanced_extractor.py

# Remove temporary configuration files
rm -f temp_config.json 
rm -f failed_queries_20250311_111156.log
rm -f workflow.log
rm -f workflow_statistics.json

# Clean extracted output files (keep the directories)
rm -f incremental_cypher/*
rm -f extracted_entities/*
rm -f compliance_context.json
rm -f final_cypher.json

# Remove redundant entity extraction prompt (we now use enhanced version)
rm -f entity_extraction_prompt.txt

# Remove temporary test files
rm -f test_cypher_gen.py

# Clean old venv directories if not needed
# Uncomment these if they're not actively used
# rm -rf docling_venv
# rm -rf docling_venv_py310

echo "Cleanup complete. Repository structure simplified."