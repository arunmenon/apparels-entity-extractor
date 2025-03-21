#!/bin/bash
# Script to load both fashion and toys taxonomy data into Neo4j
# This script preserves the existing compliance taxonomy data

# Neo4j connection parameters
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"

# Prompt for password securely (it won't be visible or saved in history)
read -sp "Enter Neo4j password: " NEO4J_PASSWORD
echo ""  # Add a newline after password input

# Path to taxonomy files
FASHION_FILE="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/fashion_augmented_taxonomy.json"
TOYS_FILE="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/toys_augmented_taxonomy.json"

# Log file
LOG_DIR="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/logs"
mkdir -p $LOG_DIR
FASHION_LOG="$LOG_DIR/fashion_load_$(date +%Y%m%d_%H%M%S).log"
TOYS_LOG="$LOG_DIR/toys_load_$(date +%Y%m%d_%H%M%S).log"

echo "===== Loading Product Taxonomies into Neo4j ====="
echo "This process will:"
echo "1. Keep all existing graph data (including compliance taxonomy)"
echo "2. Load fashion product taxonomy with attributes"
echo "3. Load toys product taxonomy with attributes"
echo "Both taxonomies will be added to the existing graph."
echo ""

# Check if files exist
if [ ! -f "$FASHION_FILE" ]; then
  echo "Error: Fashion taxonomy file not found at $FASHION_FILE"
  exit 1
fi

if [ ! -f "$TOYS_FILE" ]; then
  echo "Error: Toys taxonomy file not found at $TOYS_FILE"
  exit 1
fi

# Step 1: Load fashion taxonomy
echo "Loading fashion taxonomy data..."
python /Users/arunmenon/projects/apparels-entity-extractor/scripts/catalog_taxonomy_loader.py \
  --input "$FASHION_FILE" \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USER" \
  --password "$NEO4J_PASSWORD" \
  --log "$FASHION_LOG"

if [ $? -ne 0 ]; then
  echo "Error loading fashion taxonomy. Check log at $FASHION_LOG"
  exit 1
fi

echo "Fashion taxonomy loaded successfully!"
echo "Log file: $FASHION_LOG"
echo ""

# Step 2: Load toys taxonomy
echo "Loading toys taxonomy data..."
python /Users/arunmenon/projects/apparels-entity-extractor/scripts/catalog_taxonomy_loader.py \
  --input "$TOYS_FILE" \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USER" \
  --password "$NEO4J_PASSWORD" \
  --log "$TOYS_LOG"

if [ $? -ne 0 ]; then
  echo "Error loading toys taxonomy. Check log at $TOYS_LOG"
  exit 1
fi

echo "Toys taxonomy loaded successfully!"
echo "Log file: $TOYS_LOG"
echo ""

echo "===== Loading Complete ====="
echo "Both taxonomies have been loaded into the Neo4j database."
echo "The graph now contains:"
echo "- Original compliance taxonomy (preserved)"
echo "- Fashion product taxonomy with attributes"
echo "- Toys product taxonomy with attributes"
echo ""
echo "You can verify the loaded data with these Cypher queries:"
echo "MATCH (c:ProductCategory) RETURN c.name, count(*);"
echo "MATCH (ptg:ProductTypeGroup) RETURN count(*);"
echo "MATCH (pt:ProductType) RETURN count(*);"
echo "MATCH (a:Attribute) RETURN count(*);"
echo "MATCH (pt:ProductType)-[r:HAS_ATTRIBUTE]->(a:Attribute) RETURN count(*);"