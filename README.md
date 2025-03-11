# Compliance Entity Extraction & Knowledge Graph

## Overview
This project leverages **Large Language Models (LLM)** to extract structured compliance data from **Prohibited/Allowed Content Guides** and transform them into a knowledge graph. The system can process compliance guidelines to identify prohibited and allowed rules for various content categories, such as firearms, ammunition, or other regulated items.

The solution extracts key information hierarchically, ensuring that the content maintains its intended structure, clearly identifying what is prohibited versus what is allowed, and capturing relevant attributes.

## Key Features
- **Entity Extraction**: Uses LLM to analyze compliance PDFs and extract structured entities with clear prohibited/allowed designations
- **Rule Identification**: Identifies various rule types (Imperium Rules, Policy Rules, Image Detection Rules) with their attributes
- **Attribute Extraction**: Captures specific attributes (e.g., caliber, material, purpose) that define prohibited or allowed items
- **Knowledge Graph Integration**: Loads extracted data into a graph database with a schema optimized for compliance queries
- **Multi-Threaded Processing**: Supports multi-threaded image conversion and LLM processing to handle multiple pages in parallel
- **Imperium Rules Integration**: Processes rule expressions from the Imperium Rules DB into structured graph objects

## Knowledge Graph Schema
- **Offensive_Content_Category**: Top-level categorization (e.g., "Firearms & Accessories")
- **Sub_Category**: Specific categories (e.g., "Ammunition Production", "Armorers' Wrenches")
- **Guideline**: High-level compliance guideline text
- **Imperium_Rule**: Rules with explicit IDs (e.g., rule_id: 5374)
- **Policy_Rule**: Textual or policy-based rules
- **Image_Detection_Rule**: Rules derived from visual examples
- **Visual_Example**: Reference images with allowed/prohibited classification
- **Attribute**: Properties like caliber, material, or purpose tied to specific rules

## How it Works
1. **PDF Conversion**: The system converts PDF pages into images for further processing
2. **LLM-Based Extraction**: Images are processed by a GPT-based LLM model, which extracts entities in a structured JSON format
3. **Rule Classification**: Each rule is explicitly classified as PROHIBITS or ALLOWS
4. **Attribute Identification**: Specific attributes related to each rule are extracted
5. **Graph Database Loading**: Extracted data is converted to Cypher queries and loaded into Neo4j or TigerGraph

## Configuration
The system uses a configurable `config.json` file to define key parameters. Below is a sample configuration:

```json
{
  "api_model": "gpt-4o",
  "image_threads": 6,
  "gpt4_threads": 3
}
```

## File Structure
- **entity_extractor.py**: Main script for processing images and extracting entities
- **pdf_to_images.py**: Converts PDF documents to images
- **compliance_graph_loader.py**: Loads extracted entities into a graph database
- **graph_db/**: Contains database interface and implementation classes
- **extracted_entities/**: Stores the extracted JSON files for each processed page
- **rule_expression_parser.py**: Parses Imperium rule expressions into structured JSON
- **rule_graph_loader.py**: Loads parsed rule expressions into the graph database
- **process_imperium_rules.py**: Main script for processing Imperium rules

## How to Run
1. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Make sure `poppler` is installed for PDF to image conversion:
   ```bash
   brew install poppler  # for MacOS users
   ```
3. Convert PDF to images:
   ```bash
   python pdf_to_images.py --pdf_path <path_to_pdf>
   ```
4. Extract entities from images:
   ```bash
   python entity_extractor.py
   ```
5. Load entities into graph database:
   ```bash
   python compliance_graph_loader.py
   ```

6. Test the Imperium rule processing flow (currently disabled in main flow):
   ```bash
   # Run test with mock data
   python test_rule_flow.py
   
   # Note: The main Imperium rule processing flow is currently disabled
   # To enable it, edit process_imperium_rules.py and uncomment the implementation
   ```
   
   When enabled, the Imperium rule processing can be used as follows:
   ```bash
   # Test with a small sample
   python process_imperium_rules.py --parse --num-rules 5
   
   # Load parsed rules into graph
   python process_imperium_rules.py --load
   
   # Run the complete workflow
   python process_imperium_rules.py --all --num-rules 100
   ```

## Example Output
```json
{
  "cypher_query": "
    MERGE (occ:Offensive_Content_Category {name: 'Firearms & Accessories'})
    MERGE (sc:Sub_Category {name: 'Ammo Dies, Shell Holders & Plates'})
    MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc)
    
    MERGE (g:Guideline {description: 'Specific ammo dies, shell holders, and plates are prohibited because they are intended for pistol and assault rifle caliber products.'})
    MERGE (sc)-[:HAS_GUIDELINE]->(g)

    WITH g, sc
    UNWIND [
      {description: 'Prohibit ammo dies for calibers: 223, 224, 25, 32, 357, 38, 380, 40, 44, 45, 410 Judge, 5.56mm, 7.62x39mm, 9mm, 300 blackout', status: 'PROHIBITS', attributes: [
        {type: 'caliber', value: '223'},
        {type: 'caliber', value: '9mm'}
      ]}
    ] AS pol
    MERGE (pr:Policy_Rule {description: pol.description})
    MERGE (g)-[:PROHIBITS]->(pr)
    FOREACH (attr IN pol.attributes |
      MERGE (a:Attribute {type: attr.type, value: attr.value})
      MERGE (pr)-[:EXTRACTS_ATTRIBUTE]->(a)
      MERGE (a)-[:TIED_TO]->(sc)
    )
  "
}
```

## Conclusion
This system enables efficient processing of compliance guidelines, creating a structured knowledge graph that clearly identifies prohibited and allowed content with their specific attributes, supporting compliance enforcement and search applications.