# Taxonomy Graph Database System

This directory contains taxonomy data and tools for loading and querying graph-based taxonomies in Neo4j. The system supports various taxonomies covering different domains.

## Taxonomies Available

- **`weapons_taxonomy_graph_merged.json`**: Hierarchical weapon categories, compliance areas, and regulations
- **`compliance_taxonomy.json`**: Generic compliance and regulatory framework
- **`media_taxonomy.json`**: Media content classification and regulatory structure
- **`enhanced_nudity_taxonomy.json`**: Comprehensive nudity classification with regulatory connections

## Architecture

The taxonomy system is designed with the following components:

1. **JSON-based Taxonomy Schema**:
   - Nodes representing categories, subcategories, compliance areas, and regulations
   - Edges representing relationships like parent-child, regulated-by, and governed-by

2. **Loader Framework**:
   - Generic taxonomy loader supporting various taxonomy types
   - Neo4j integration for graph database storage

3. **Verification Tools**:
   - Structure validation and integrity checking
   - Regulatory relationship analysis

4. **Querying Interface**:
   - Cypher queries for exploring taxonomy structure
   - Path-based analysis for regulatory compliance

## JSON Schema

All taxonomies follow a consistent schema:

```json
{
  "nodes": [
    {
      "id": "CategoryId",
      "type": "Category|Subcategory|ComplianceArea|Law/Regulation",
      "label": "Human-readable name",
      "description": "Detailed description"
    }
  ],
  "edges": [
    {
      "source": "SourceNodeId",
      "target": "TargetNodeId",
      "relationship": "<parent_of>|<regulated_by>|<governed_by>|<regulated_under>|<implements>",
      "properties": {
        "notes": ["Optional additional info"],
        "description": "Optional relationship description"
      }
    }
  ]
}
```

## Using the Taxonomy System

### Loading a Taxonomy

```bash
./load_taxonomy.sh taxonomy/weapons_taxonomy_graph_merged.json
```

### Verifying a Taxonomy

```bash
python3 verify_taxonomy.py --root Weapons
```

### Running Queries

Refer to the Cypher queries in `taxonomy/example_queries.cypher` for examples.

## Extending the System

To add a new taxonomy:

1. Create a new JSON file following the schema above
2. Place it in the taxonomy directory
3. Load it using the generic loader script
4. Verify its structure with the verification tool

## Legacy Support

The system maintains backward compatibility with the old taxonomy structure:
- Original Neo4j schema with Product_Category, Compliance_Area, etc.
- Support for old-style relationship types (HAS_COMPLIANCE_AREA, etc.)
- Legacy API for querying older taxonomies

## Best Practices

- Use consistent naming conventions for node IDs
- Ensure hierarchical relationships are properly defined
- Connect subcategories to appropriate compliance areas
- Link compliance areas to relevant laws and regulations

## Prerequisites

- Neo4j installed and running
- Python 3.6+ with neo4j-driver package
- Default Neo4j credentials configured in the scripts