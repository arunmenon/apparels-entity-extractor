#!/bin/bash
# Generic script to load any taxonomy into Neo4j with conditional database clearing

# Get the taxonomy file path from command line arguments or use default
TAXONOMY_FILE=$1
if [ -z "$TAXONOMY_FILE" ]; then
    echo "Usage: ./load_taxonomy.sh <taxonomy_file_path> [--clear]"
    echo "Example: ./load_taxonomy.sh taxonomy/nudity_taxonomy.json --clear"
    echo "The --clear flag is optional. If provided, the database will be cleared before loading."
    exit 1
fi

# Check if the clear flag is provided
CLEAR_DB=false
if [[ "$*" == *"--clear"* ]]; then
    CLEAR_DB=true
fi

# Extract taxonomy name from file path for logging
TAXONOMY_NAME=$(basename "$TAXONOMY_FILE" .json)
echo "Loading taxonomy: $TAXONOMY_NAME from $TAXONOMY_FILE"

# Set Neo4j connection parameters
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="Rathum12!"
NEO4J_DATABASE="neo4j"

# Step 1: Clear the database if requested
if [ "$CLEAR_DB" = true ]; then
    echo "Clearing the Neo4j database..."
    python3 scripts/clear_graph.py
else
    echo "Skipping database clearing. Using existing database content."
fi

# Step 2: Load the taxonomy
echo "Loading the taxonomy..."
python3 taxonomy_loader.py \
    --taxonomy-file "$TAXONOMY_FILE" \
    --db-type neo4j \
    --uri "$NEO4J_URI" \
    --username "$NEO4J_USER" \
    --password "$NEO4J_PASSWORD" \
    --database "$NEO4J_DATABASE"

# Check if the taxonomy loader was successful
if [ $? -eq 0 ]; then
    echo "Successfully loaded taxonomy: $TAXONOMY_NAME"
else
    echo "Failed to load taxonomy: $TAXONOMY_NAME"
    exit 1
fi

echo "Done!"