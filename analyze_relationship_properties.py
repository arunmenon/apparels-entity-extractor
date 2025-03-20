#!/usr/bin/env python3
"""
Generate relationship property metadata for improved schema understanding.

This script analyzes the graph database and builds a comprehensive property metadata
index that includes data types, statistics, and semantic roles for all properties.
This helps the LLM understand the purpose and meaningful values for these properties.
"""

import json
import statistics
from graph_db.neo4j_database import Neo4jDatabase

def analyze_property_statistics(values):
    """Calculate statistical metrics for numeric values"""
    if not values:
        return {}
    
    # Filter out None values
    valid_values = [v for v in values if v is not None]
    
    if not valid_values:
        return {}
    
    try:
        sorted_values = sorted(valid_values)
        return {
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": statistics.mean(valid_values),
            "median": statistics.median(valid_values),
            "p75": sorted_values[int(len(sorted_values) * 0.75)] if len(sorted_values) >= 4 else sorted_values[-1],
            "p90": sorted_values[int(len(sorted_values) * 0.9)] if len(sorted_values) >= 10 else sorted_values[-1],
            "high_threshold": sorted_values[int(len(sorted_values) * 0.7)] if len(sorted_values) >= 3 else 0.7
        }
    except Exception as e:
        print(f"Error calculating statistics: {e}")
        return {}

def infer_property_type(values):
    """Infer the data type of a property based on sample values"""
    if not values or all(v is None for v in values):
        return "unknown"
    
    non_null_values = [v for v in values if v is not None]
    if not non_null_values:
        return "unknown"
    
    sample = non_null_values[0]
    
    # Numeric types
    if isinstance(sample, (int, float)):
        if all(isinstance(v, int) for v in non_null_values):
            return "integer"
        return "numeric"
    
    # String types
    if isinstance(sample, str):
        if all(len(v) > 100 for v in non_null_values):
            return "long_text"
        return "text"
    
    # Boolean
    if isinstance(sample, bool):
        return "boolean"
    
    # Lists
    if isinstance(sample, list):
        return "list"
    
    return "other"

def infer_semantic_role(property_name, property_type, values):
    """Infer the semantic meaning of a property based on name and content patterns"""
    property_name_lower = property_name.lower()
    
    # Confidence measures
    if ('confidence' in property_name_lower or 
        'score' in property_name_lower or 
        'weight' in property_name_lower or
        'probability' in property_name_lower):
        return "confidence_measure"
    
    # Explanatory text
    if ('reason' in property_name_lower or 
        'explanation' in property_name_lower or 
        'description' in property_name_lower or
        'notes' in property_name_lower):
        return "explanation"
    
    # Timestamps
    if ('date' in property_name_lower or 
        'time' in property_name_lower or 
        'created' in property_name_lower or
        'updated' in property_name_lower):
        return "timestamp"
    
    # Identifiers
    if ('id' in property_name_lower or 
        'key' in property_name_lower or 
        'uuid' in property_name_lower):
        return "identifier"
    
    # Default based on type
    if property_type == "numeric":
        return "measurement"
    if property_type == "long_text":
        return "description"
    if property_type == "boolean":
        return "flag"
    
    return "attribute"

def analyze_relationship_properties():
    """Analyze all relationship properties in the Neo4j database"""
    print("Connecting to Neo4j...")
    db = Neo4jDatabase(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="Rathum12!",
        database="neo4j"
    )
    
    try:
        db.connect()
        print("Connection successful!")
        
        # Get all relationship types
        rel_types_query = """
        MATCH ()-[r]->()
        RETURN DISTINCT type(r) AS relationship_type
        """
        rel_types_results = db.execute_query(rel_types_query)
        rel_types = [r.get('relationship_type') for r in rel_types_results]
        
        property_metadata = {}
        
        for rel_type in rel_types:
            print(f"Analyzing properties for {rel_type}...")
            
            # Get all properties for this relationship type
            properties_query = f"""
            MATCH ()-[r:{rel_type}]->()
            UNWIND keys(r) AS property_name
            RETURN DISTINCT property_name
            """
            
            properties_results = db.execute_query(properties_query)
            properties = [p.get('property_name') for p in properties_results]
            
            if not properties:
                print(f"  No properties found for {rel_type}")
                continue
                
            print(f"  Found properties: {', '.join(properties)}")
            property_metadata[rel_type] = {}
            
            # For each property, collect sample values and statistics
            for prop in properties:
                print(f"  Analyzing {prop}...")
                
                # Get sample values
                values_query = f"""
                MATCH ()-[r:{rel_type}]->()
                WHERE r.{prop} IS NOT NULL
                RETURN r.{prop} AS value
                LIMIT 100
                """
                
                values_results = db.execute_query(values_query)
                values = [r.get('value') for r in values_results]
                
                # Get source and target node labels
                connections_query = f"""
                MATCH (source)-[r:{rel_type}]->(target)
                WHERE r.{prop} IS NOT NULL
                RETURN DISTINCT
                  labels(source)[0] AS source_label,
                  labels(target)[0] AS target_label
                LIMIT 5
                """
                
                connections_results = db.execute_query(connections_query)
                connections = [
                    {
                        "source": r.get('source_label'),
                        "target": r.get('target_label')
                    } for r in connections_results
                ]
                
                # Infer property type and semantic role
                property_type = infer_property_type(values)
                semantic_role = infer_semantic_role(prop, property_type, values)
                
                # Calculate statistics for numeric properties
                statistics_data = {}
                if property_type in ('numeric', 'integer'):
                    statistics_data = analyze_property_statistics(values)
                
                # Build metadata for this property
                property_metadata[rel_type][prop] = {
                    "type": property_type,
                    "semantic_role": semantic_role,
                    "connections": connections,
                    "statistics": statistics_data,
                    "sample_values": values[:5] if property_type != "long_text" else [v[:100] + "..." if v and len(v) > 100 else v for v in values[:3]]
                }
        
        # Save the metadata to a file
        with open('relationship_property_metadata.json', 'w') as f:
            json.dump(property_metadata, f, indent=2)
            
        print(f"Saved property metadata to relationship_property_metadata.json")
        
        # Extract and print common patterns
        print("\nCommon patterns:")
        
        # Find relationships with confidence measures
        confidence_rels = []
        for rel_type, props in property_metadata.items():
            for prop, metadata in props.items():
                if metadata['semantic_role'] == 'confidence_measure':
                    connections = metadata.get('connections', [])
                    stats = metadata.get('statistics', {})
                    if connections and stats:
                        for conn in connections:
                            high_threshold = stats.get('high_threshold', 0.7)
                            confidence_rels.append({
                                "relationship": rel_type,
                                "property": prop,
                                "source": conn.get('source'),
                                "target": conn.get('target'),
                                "high_threshold": high_threshold
                            })
        
        if confidence_rels:
            print("Relationships with confidence measures:")
            for rel in confidence_rels:
                print(f"  ({rel['source']})-[:{rel['relationship']}]-({rel['target']}) with {rel['property']} >= {rel['high_threshold']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        db.close()
        print("Connection closed")

if __name__ == "__main__":
    analyze_relationship_properties()