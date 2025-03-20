# Relationship Property Metadata Integration

## Overview

This document outlines the integration of relationship property metadata into the Graph RAG system. This enhancement enables dynamic discovery and use of relationship properties with their semantics, types, and statistical information.

## Components Modified

1. **SchemaManager Class**
   - Added property_metadata loading in __init__
   - Updated format_schema_for_prompt to include property type, role, and thresholds
   - Enhanced format_rich_context_for_prompt with property information and example queries
   - Added automatic detection of the relationship_property_metadata.json file

2. **Query Decomposition Prompt**
   - Updated to instruct the LLM to use the thresholds from the schema
   - Added guidelines for properly handling confidence measures
   - Added instructions for including explanation properties in results
   - Emphasized path-based queries for hierarchical relationships

## Key Benefits

- **Dynamic Threshold Discovery**: System now uses statistically derived thresholds (e.g., 0.4 for MAY_VIOLATE) rather than hardcoded values
- **Property Type Awareness**: Schema now includes type information (numeric, text, long_text, boolean)
- **Semantic Role Understanding**: Properties are classified by role (confidence_measure, explanation, attribute, identifier)
- **Statistical Range Information**: Numeric properties include min, max, mean, and threshold values
- **Rich Context Enhancement**: Query examples and property information in rich context
- **Example-Driven Guidance**: LLM gets concrete examples of using properties and thresholds

## Testing

Created test_metadata_integration.py to verify:
- Schema includes confidence measures section
- Rich context includes property information
- MAY_VIOLATE relationship with threshold is properly detected

## Example Schema Output

The enhanced schema now includes sections like:

```
Relationships with Confidence Measures:
- (ProductType)-[:MAY_VIOLATE]->(Subcategory) with confidence_score >= 0.4
```

## Example Rich Context Output

The rich context now includes sections like:

```
Relationship Property Information:

MAY_VIOLATE.confidence_score:
  - Type: numeric
  - Role: confidence_measure
  - Used in: (ProductType)->(Subcategory)
  - Range: 0.2 to 0.92
  - High threshold: >= 0.4
  - Sample values: 0.2; 0.2; 0.2

MAY_VIOLATE.reasoning:
  - Type: long_text
  - Role: explanation
  - Used in: (ProductType)->(Subcategory)
  - Sample values: Rain umbrellas are not firearms...
```

## Next Steps

1. Extend schema manager to include property statistics in the main schema JSON
2. Add relationship property examples directly to the common queries section
3. Implement automated tests for validation against new relationship types
4. Add documentation for custom property semantic role creation