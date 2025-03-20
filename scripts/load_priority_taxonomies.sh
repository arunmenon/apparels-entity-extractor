#!/bin/bash
# Script to load priority taxonomies into Neo4j

# Set Neo4j credentials and URI
NEO4J_URI=$(grep -v "OPENAI_API_KEY" /Users/arunmenon/projects/apparels-entity-extractor/neo4j_uri.txt | head -n 1)
NEO4J_USERNAME="neo4j"
NEO4J_PASSWORD=$(grep "NEO4J_PASSWORD" /Users/arunmenon/projects/apparels-entity-extractor/neo4j_uri.txt | cut -d= -f2)

# Check if processes are complete
check_process() {
  local pid=$1
  local name=$2
  if ps -p $pid > /dev/null; then
    echo "$name augmentation still running with PID $pid"
    echo "To check progress: tail -f priority_output/$name/augment_log.txt"
    return 1
  else
    echo "$name augmentation complete"
    return 0
  fi
}

# Define paths
PROJECT_ROOT="/Users/arunmenon/projects/apparels-entity-extractor"
FASHION_PATH="$PROJECT_ROOT/priority_output/fashion/augmented_taxonomy.json"
ARTS_CRAFTS_PATH="$PROJECT_ROOT/priority_output/arts_crafts/augmented_taxonomy.json"
GARDEN_PATIO_PATH="$PROJECT_ROOT/priority_output/garden_patio/augmented_taxonomy.json"

# Check if all processes have completed
echo "Checking if augmentation processes have completed..."

fashion_pid=$(cat $PROJECT_ROOT/priority_output/fashion/fashion_pid.txt)
arts_crafts_pid=$(cat $PROJECT_ROOT/priority_output/arts_crafts/arts_crafts_pid.txt)
garden_patio_pid=$(cat $PROJECT_ROOT/priority_output/garden_patio/garden_patio_pid.txt)

all_complete=true

check_process $fashion_pid "fashion" || all_complete=false
check_process $arts_crafts_pid "arts_crafts" || all_complete=false
check_process $garden_patio_pid "garden_patio" || all_complete=false

if [ "$all_complete" = false ]; then
  echo "Not all augmentation processes have completed. Please try again later."
  exit 1
fi

# Check if output files exist
echo "Checking if output files exist..."
missing_files=false

if [ ! -f "$FASHION_PATH" ]; then
  echo "Fashion taxonomy file not found: $FASHION_PATH"
  missing_files=true
fi

if [ ! -f "$ARTS_CRAFTS_PATH" ]; then
  echo "Arts & Crafts taxonomy file not found: $ARTS_CRAFTS_PATH"
  missing_files=true
fi

if [ ! -f "$GARDEN_PATIO_PATH" ]; then
  echo "Garden & Patio taxonomy file not found: $GARDEN_PATIO_PATH"
  missing_files=true
fi

if [ "$missing_files" = true ]; then
  echo "Some output files are missing. Please check the augmentation logs."
  exit 1
fi

# Load taxonomies into Neo4j
echo "Loading taxonomies into Neo4j..."

# Fashion
echo "Loading Fashion taxonomy..."
python $PROJECT_ROOT/scripts/catalog_taxonomy_loader.py \
  --input "$FASHION_PATH" \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USERNAME" \
  --password "$NEO4J_PASSWORD" \
  --log "$PROJECT_ROOT/priority_output/fashion/neo4j_load.log"

# Arts & Crafts
echo "Loading Arts & Crafts taxonomy..."
python $PROJECT_ROOT/scripts/catalog_taxonomy_loader.py \
  --input "$ARTS_CRAFTS_PATH" \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USERNAME" \
  --password "$NEO4J_PASSWORD" \
  --log "$PROJECT_ROOT/priority_output/arts_crafts/neo4j_load.log"

# Garden & Patio
echo "Loading Garden & Patio taxonomy..."
python $PROJECT_ROOT/scripts/catalog_taxonomy_loader.py \
  --input "$GARDEN_PATIO_PATH" \
  --uri "$NEO4J_URI" \
  --username "$NEO4J_USERNAME" \
  --password "$NEO4J_PASSWORD" \
  --log "$PROJECT_ROOT/priority_output/garden_patio/neo4j_load.log"

echo "Taxonomy loading complete!"
echo "You can now run the product compliance connector to analyze these categories against Nudity and Weapons compliance categories."