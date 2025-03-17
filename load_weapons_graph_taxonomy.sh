#!/bin/bash
# Script to clear the Neo4j database and load the merged weapons taxonomy

echo "Clearing the Neo4j database..."
python3 scripts/clear_graph.py

echo "Loading the merged weapons taxonomy..."
python3 load_weapons_graph_taxonomy.py --taxonomy-file /Users/arunmenon/projects/apparels-entity-extractor/taxonomy/weapons_taxonomy_graph_merged.json

echo "Done!"