#!/bin/bash
# Script to load compliance analysis data from batch analysis files

# Neo4j connection parameters
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"

# Prompt for password securely
read -sp "Enter Neo4j password: " NEO4J_PASSWORD
echo ""  # Add newline after password input

# Directory paths to compliance batch analysis files
FASHION_NUDITY_DIR="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Fashion_Nudity"
FASHION_WEAPONS_DIR="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Fashion_Weapons"
ARTS_CRAFTS_NUDITY_DIR="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Arts & Crafts_Nudity"
GARDEN_PATIO_WEAPONS_DIR="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Garden & Patio_Weapons"

# Create a temporary Python script to process the files
TMP_SCRIPT="/tmp/load_batch_analysis_$$.py"

cat > $TMP_SCRIPT << 'EOF'
#!/usr/bin/env python3
import json
import sys
import argparse
import os
import glob
from neo4j import GraphDatabase

def load_batch_analysis(uri, user, password, directory, min_confidence=0.2):
    """Load MAY_VIOLATE relationships from batch analysis files"""
    
    # Find all analysis_batch_*.json files
    batch_files = glob.glob(os.path.join(directory, "analysis_batch_*.json"))
    
    if not batch_files:
        print(f"No analysis batch files found in {directory}")
        return
    
    print(f"Found {len(batch_files)} batch files in {directory}")
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # Process each batch file
    for batch_file in sorted(batch_files):
        print(f"Processing {os.path.basename(batch_file)}...")
        
        # Load the batch analysis data
        with open(batch_file, 'r') as f:
            batch_data = json.load(f)
        
        # Prepare queries for relationships with confidence score >= min_confidence
        queries = []
        for item in batch_data:
            product = item.get('product', {})
            product_type = product.get('product_type', '')
            subcategory_id = item.get('subcategory_id', '')
            analysis = item.get('analysis', {})
            confidence_score = analysis.get('confidence_score', 0.0)
            reasoning = analysis.get('reasoning', '')
            
            # Only create relationships for items with confidence score above threshold
            if confidence_score >= min_confidence:
                # Escape string values for Cypher
                product_type_escaped = product_type.replace("'", "\\'")
                subcategory_id_escaped = subcategory_id.replace("'", "\\'")
                reasoning_escaped = reasoning.replace("'", "\\'")
                
                # Create Cypher query
                query = f"""
                MATCH (pt:ProductType {{name: '{product_type_escaped}'}})
                MATCH (sub:Subcategory {{id: '{subcategory_id_escaped}'}})
                MERGE (pt)-[r:MAY_VIOLATE {{
                    confidence_score: {confidence_score},
                    reasoning: '{reasoning_escaped}'
                }}]->(sub)
                """
                queries.append(query)
        
        # Execute queries in batches
        batch_size = 50
        with driver.session() as session:
            for i in range(0, len(queries), batch_size):
                current_batch = queries[i:i+batch_size]
                print(f"Executing batch {i//batch_size + 1}/{(len(queries)-1)//batch_size + 1} with {len(current_batch)} queries...")
                
                for query in current_batch:
                    try:
                        session.run(query)
                    except Exception as e:
                        print(f"Error: {str(e)}")
    
    # Close the connection
    driver.close()
    print(f"Finished processing directory: {directory}")

def main():
    parser = argparse.ArgumentParser(description="Load MAY_VIOLATE relationships from batch analysis files")
    parser.add_argument("--uri", required=True, help="Neo4j URI")
    parser.add_argument("--username", required=True, help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--directory", required=True, help="Directory containing analysis batch files")
    parser.add_argument("--min-confidence", type=float, default=0.2, help="Minimum confidence score threshold (default: 0.2)")
    
    args = parser.parse_args()
    load_batch_analysis(args.uri, args.username, args.password, args.directory, args.min_confidence)

if __name__ == "__main__":
    main()
EOF

chmod +x $TMP_SCRIPT

# Function to check if directory exists
check_dir() {
    if [ ! -d "$1" ]; then
        echo "Warning: Directory not found: $1"
        return 1
    fi
    return 0
}

# Load relationships from each directory
echo "===== Loading MAY_VIOLATE Relationships from Batch Analysis Files ====="

if check_dir "$FASHION_NUDITY_DIR"; then
    echo "Loading Fashion-Nudity MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --directory "$FASHION_NUDITY_DIR"
    echo ""
fi

if check_dir "$FASHION_WEAPONS_DIR"; then
    echo "Loading Fashion-Weapons MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --directory "$FASHION_WEAPONS_DIR"
    echo ""
fi

if check_dir "$ARTS_CRAFTS_NUDITY_DIR"; then
    echo "Loading Arts & Crafts-Nudity MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --directory "$ARTS_CRAFTS_NUDITY_DIR"
    echo ""
fi

if check_dir "$GARDEN_PATIO_WEAPONS_DIR"; then
    echo "Loading Garden & Patio-Weapons MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --directory "$GARDEN_PATIO_WEAPONS_DIR"
    echo ""
fi

# Clean up temporary script
rm $TMP_SCRIPT

echo "===== Loading Complete ====="
echo "MAY_VIOLATE relationships have been loaded into the Neo4j database."
echo ""
echo "You can verify the loaded data with these Cypher queries:"
echo "MATCH (pt:ProductType)-[r:MAY_VIOLATE]->(sub:Subcategory) RETURN count(r);"
echo "MATCH (pt:ProductType)-[r:MAY_VIOLATE]->(sub:Subcategory) RETURN pt.name, sub.name, r.confidence_score ORDER BY r.confidence_score DESC LIMIT 10;"