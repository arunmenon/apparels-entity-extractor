#!/bin/bash
# Script to load MAY_VIOLATE relationships between ProductType and Subcategory

# Neo4j connection parameters
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"

# Prompt for password securely
read -sp "Enter Neo4j password: " NEO4J_PASSWORD
echo ""  # Add newline after password input

# Path to compliance graph structure files
FASHION_NUDITY_FILE="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Fashion_Nudity/graph_structure.json"
FASHION_WEAPONS_FILE="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Fashion_Weapons/graph_structure.json"
ARTS_CRAFTS_NUDITY_FILE="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Arts & Crafts_Nudity/graph_structure.json" 
GARDEN_PATIO_WEAPONS_FILE="/Users/arunmenon/projects/apparels-entity-extractor/product_taxonomy/Garden & Patio_Weapons/graph_structure.json"

# Create a temporary Python script to process the files
TMP_SCRIPT="/tmp/load_relationships_$$.py"

cat > $TMP_SCRIPT << 'EOF'
#!/usr/bin/env python3
import json
import sys
import argparse
from neo4j import GraphDatabase

def load_may_violate_relationships(uri, user, password, file_path):
    """Load only MAY_VIOLATE relationships from graph structure file"""
    
    # Load the graph structure file
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Extract only the MAY_VIOLATE relationships
    may_violate_edges = [edge for edge in data.get('edges', []) 
                        if edge.get('relationship') == 'MAY_VIOLATE']
    
    print(f"Found {len(may_violate_edges)} MAY_VIOLATE relationships in {file_path}")
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # Create Cypher queries for the relationships
    queries = []
    for edge in may_violate_edges:
        source_id = edge.get('source', '').replace("'", "\\'")
        target_id = edge.get('target', '').replace("'", "\\'")
        props = edge.get('properties', {})
        
        # Create properties string
        props_list = []
        for key, value in props.items():
            if isinstance(value, str):
                value = value.replace("'", "\\'")
                props_list.append(f"{key}: '{value}'")
            elif value is not None:
                props_list.append(f"{key}: {value}")
        
        props_str = "{" + ", ".join(props_list) + "}" if props_list else ""
        
        # Create the query
        query = f"""
        MATCH (pt:ProductType {{name: '{source_id}'}})
        MATCH (sub:Subcategory {{id: '{target_id}'}})
        MERGE (pt)-[r:MAY_VIOLATE {props_str}]->(sub)
        """
        queries.append(query)
    
    # Execute queries in batches
    batch_size = 50
    successful = 0
    failed = 0
    
    with driver.session() as session:
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i+batch_size]
            print(f"Executing batch {i//batch_size + 1}/{(len(queries)-1)//batch_size + 1}...")
            
            for query in batch:
                try:
                    session.run(query)
                    successful += 1
                except Exception as e:
                    print(f"Error: {str(e)}")
                    print(f"Failed query: {query[:100]}...")
                    failed += 1
    
    # Close the connection
    driver.close()
    
    print(f"Finished loading relationships. Success: {successful}, Failed: {failed}")

def main():
    parser = argparse.ArgumentParser(description="Load MAY_VIOLATE relationships from graph structure file")
    parser.add_argument("--uri", required=True, help="Neo4j URI")
    parser.add_argument("--username", required=True, help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--file", required=True, help="Path to graph structure JSON file")
    
    args = parser.parse_args()
    load_may_violate_relationships(args.uri, args.username, args.password, args.file)

if __name__ == "__main__":
    main()
EOF

chmod +x $TMP_SCRIPT

# Function to check if file exists
check_file() {
    if [ ! -f "$1" ]; then
        echo "Warning: File not found: $1"
        return 1
    fi
    return 0
}

# Load relationships from each file
echo "===== Loading MAY_VIOLATE Relationships into Neo4j ====="

if check_file "$FASHION_NUDITY_FILE"; then
    echo "Loading Fashion-Nudity MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --file "$FASHION_NUDITY_FILE"
    echo ""
fi

if check_file "$FASHION_WEAPONS_FILE"; then
    echo "Loading Fashion-Weapons MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --file "$FASHION_WEAPONS_FILE"
    echo ""
fi

if check_file "$ARTS_CRAFTS_NUDITY_FILE"; then
    echo "Loading Arts & Crafts-Nudity MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --file "$ARTS_CRAFTS_NUDITY_FILE"
    echo ""
fi

if check_file "$GARDEN_PATIO_WEAPONS_FILE"; then
    echo "Loading Garden & Patio-Weapons MAY_VIOLATE relationships..."
    python $TMP_SCRIPT --uri "$NEO4J_URI" --username "$NEO4J_USER" --password "$NEO4J_PASSWORD" --file "$GARDEN_PATIO_WEAPONS_FILE"
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