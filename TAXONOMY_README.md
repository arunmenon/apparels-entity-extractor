# Weapons Taxonomy Graph Loader

This directory contains tools for loading a graph-based weapons taxonomy into Neo4j. The taxonomy represents weapons categories, their hierarchical relationships, and their regulatory frameworks.

## Files Overview

- **`taxonomy/weapons_taxonomy_graph_merged.json`**: The complete graph-based taxonomy with nodes and relationships
- **`load_weapons_graph_taxonomy.py`**: Python script for loading the taxonomy into Neo4j
- **`load_weapons_graph_taxonomy.sh`**: Shell script to clear the database and run the loader
- **`verify_merged_taxonomy.py`**: Script to verify the loaded taxonomy with sample queries

## Taxonomy Structure

The taxonomy is represented as a graph with:

1. **Node Types**:
   - **Category**: Root node (Weapons)
   - **Subcategory**: Weapon types and subtypes (68 nodes in total)
   - **ComplianceArea**: Regulatory domains (8 areas)
   - **Law_Regulation**: Specific laws and regulations (13 nodes)

2. **Relationship Types**:
   - **PARENT_OF**: Hierarchical connections between categories
   - **REGULATED_BY**: Links between weapon subcategories and compliance areas
   - **GOVERNED_BY**: Links between compliance areas and laws/regulations

## Prerequisites

- Neo4j installed and running
- Python 3.6+ with the neo4j-driver package
- Default Neo4j credentials configured in the scripts (neo4j/Rathum12!)

## Loading the Taxonomy

1. **Clear the database and load the taxonomy**:
   ```bash
   ./load_weapons_graph_taxonomy.sh
   ```

   This will clear any existing data in the Neo4j database and load the complete merged taxonomy.

2. **Verify the loaded taxonomy**:
   ```bash
   python3 verify_merged_taxonomy.py
   ```

   This will run several queries to show the structure of the loaded taxonomy.

## Sample Cypher Queries

### View Hierarchy

```cypher
// Complete subcategory hierarchy with indentation to show levels
MATCH path = (root:Category {id: 'Weapons'})-[:PARENT_OF*1..5]->(child:Subcategory)
WITH child, length(path) AS depth
MATCH (parent)-[:PARENT_OF]->(child)
WHERE parent:Category OR parent:Subcategory
RETURN 
  CASE 
    WHEN depth = 1 THEN child.id
    WHEN depth = 2 THEN "  ├── " + child.id
    WHEN depth = 3 THEN "  │   ├── " + child.id
    WHEN depth = 4 THEN "  │   │   ├── " + child.id
    WHEN depth = 5 THEN "  │   │   │   ├── " + child.id
    ELSE "  │   │   │   │   ├── " + child.id
  END AS hierarchy,
  child.label AS description,
  depth,
  parent.id AS parent
ORDER BY depth, child.id;
```

### View Compliance Areas for a Weapon Type

```cypher
MATCH (s:Subcategory {id: 'Firearms'})-[r:REGULATED_BY]->(ca:ComplianceArea)
RETURN ca.id AS compliance_area,
       r.notes AS regulations
ORDER BY compliance_area;
```

### View Complete Regulatory Path

```cypher
MATCH path = (s:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)
             -[:GOVERNED_BY]->(l:Law_Regulation)
RETURN s.id AS subcategory, ca.id AS compliance_area, l.id AS law
ORDER BY ca.id, l.id;
```

## Customizing the Taxonomy

To modify the taxonomy:

1. Edit the `taxonomy/weapons_taxonomy_graph_merged.json` file
2. Run the loader script to reload the taxonomy

You can also create entirely new taxonomies by following the same JSON structure with nodes and edges.