#!/bin/bash
# Script to run compliance analysis for priority categories

# Set Neo4j credentials and URI
NEO4J_URI=$(grep -v "OPENAI_API_KEY" /Users/arunmenon/projects/apparels-entity-extractor/neo4j_uri.txt | head -n 1)
NEO4J_USERNAME="neo4j"
NEO4J_PASSWORD=$(grep "NEO4J_PASSWORD" /Users/arunmenon/projects/apparels-entity-extractor/neo4j_uri.txt | cut -d= -f2)
OPENAI_API_KEY=$(grep "OPENAI_API_KEY" /Users/arunmenon/projects/apparels-entity-extractor/neo4j_uri.txt | cut -d= -f2)

# Define paths
PROJECT_ROOT="/Users/arunmenon/projects/apparels-entity-extractor"
OUTPUT_DIR="$PROJECT_ROOT/priority_output/compliance_analysis"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Export OpenAI API key
export OPENAI_API_KEY="$OPENAI_API_KEY"

# Run Fashion vs Nudity
echo "Analyzing Fashion products against Nudity compliance..."
FASHION_NUDITY_LOG="$OUTPUT_DIR/fashion_nudity.log"
nohup python $PROJECT_ROOT/scripts/product_compliance_connector_batch.py \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USERNAME" \
  --password "$NEO4J_PASSWORD" \
  --product-category "Fashion" \
  --compliance-category "Nudity" \
  --subcats-per-batch 2 \
  --log "$FASHION_NUDITY_LOG" \
  --debug > "$FASHION_NUDITY_LOG" 2>&1 &

FASHION_NUDITY_PID=$!
echo "Started Fashion vs Nudity analysis with PID $FASHION_NUDITY_PID"
echo $FASHION_NUDITY_PID > "$OUTPUT_DIR/fashion_nudity_pid.txt"

# Run Arts & Crafts vs Nudity
echo "Analyzing Arts & Crafts products against Nudity compliance..."
ARTS_NUDITY_LOG="$OUTPUT_DIR/arts_crafts_nudity.log"
nohup python $PROJECT_ROOT/scripts/product_compliance_connector_batch.py \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USERNAME" \
  --password "$NEO4J_PASSWORD" \
  --product-category "Arts & Crafts" \
  --compliance-category "Nudity" \
  --subcats-per-batch 2 \
  --log "$ARTS_NUDITY_LOG" \
  --debug > "$ARTS_NUDITY_LOG" 2>&1 &

ARTS_NUDITY_PID=$!
echo "Started Arts & Crafts vs Nudity analysis with PID $ARTS_NUDITY_PID"
echo $ARTS_NUDITY_PID > "$OUTPUT_DIR/arts_crafts_nudity_pid.txt"

# Run Garden & Patio vs Weapons
echo "Analyzing Garden & Patio products against Weapons compliance..."
GARDEN_WEAPONS_LOG="$OUTPUT_DIR/garden_patio_weapons.log"
nohup python $PROJECT_ROOT/scripts/product_compliance_connector_batch.py \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USERNAME" \
  --password "$NEO4J_PASSWORD" \
  --product-category "Garden & Patio" \
  --compliance-category "Weapons" \
  --subcats-per-batch 2 \
  --log "$GARDEN_WEAPONS_LOG" \
  --debug > "$GARDEN_WEAPONS_LOG" 2>&1 &

GARDEN_WEAPONS_PID=$!
echo "Started Garden & Patio vs Weapons analysis with PID $GARDEN_WEAPONS_PID"
echo $GARDEN_WEAPONS_PID > "$OUTPUT_DIR/garden_patio_weapons_pid.txt"

echo ""
echo "All compliance analysis jobs are running in the background."
echo "To monitor progress, you can use:"
echo "  tail -f $FASHION_NUDITY_LOG"
echo "  tail -f $ARTS_NUDITY_LOG"
echo "  tail -f $GARDEN_WEAPONS_LOG"
echo ""
echo "The results will be saved in the product_taxonomy directory with the format:"
echo "  product_taxonomy/Fashion_Nudity/"
echo "  product_taxonomy/Arts & Crafts_Nudity/"
echo "  product_taxonomy/Garden & Patio_Weapons/"