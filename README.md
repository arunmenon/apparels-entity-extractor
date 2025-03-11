# Compliance Entity Extraction & Knowledge Graph

## Overview
This project extracts structured compliance data from product policy documents (like Prohibited/Allowed Content Guides) and transforms them into a knowledge graph. The system processes compliance guidelines to identify what's prohibited versus allowed, capturing relevant attributes and relationships. It then connects these entities to existing Imperium rules in a Neo4j database.

## Features
- **Entity Extraction**: Uses GPT-4 Vision to analyze compliance PDFs and extract structured entities 
- **Rule Identification**: Identifies rule IDs and creates connections to existing Imperium rules
- **Smart Entity Relationships**: Handles missing rule IDs with conditional relationship creation
- **Context Awareness**: Maintains category context across multiple document pages
- **Attribute Extraction**: Captures specific attributes (e.g., caliber, material) that define rules
- **Knowledge Graph Integration**: Loads extracted data into a Neo4j graph database
- **Multi-Threaded Processing**: Handles multiple pages in parallel for faster processing
- **Hybrid TOC Processing**: Specialized detection and extraction for Table of Contents pages

## Knowledge Graph Schema
- **Offensive_Content_Category**: Top-level categories (e.g., "Firearms & Accessories")
- **Sub_Category**: Specific categories (e.g., "Ammunition", "Armorers' Wrenches")
- **Guideline**: High-level compliance guideline text
- **Imperium_Rule**: Rules with explicit IDs (matched to existing rules)
- **Policy_Rule**: Textual or policy-based rules without explicit IDs
- **Image_Detection_Rule**: Rules derived from visual examples
- **Attribute**: Properties like caliber, material, or purpose tied to specific rules

## Installation & Setup

### Prerequisites
- Python 3.9+
- Neo4j Database (Community Edition 5.x+)
- OpenAI API key (for GPT-4 Vision)
- poppler (for PDF processing)

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/apparels-entity-extractor.git
   cd apparels-entity-extractor
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install poppler for PDF processing:
   ```bash
   # macOS
   brew install poppler
   
   # Ubuntu/Debian
   sudo apt-get install poppler-utils
   
   # Windows (use conda)
   conda install -c conda-forge poppler
   ```

5. Set up environment variables by creating a `.env` file:
   ```
   OPENAI_API_KEY=your_openai_api_key
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_neo4j_password
   BATCH_SIZE=20
   ```

## Workflow

### 1. Convert PDF to Images
Convert your compliance PDF document into images for processing:

```bash
# Use the default settings (looks for PDF at ~/Downloads/compliance_document.pdf)
python pdf_to_images.py

# Specify a custom PDF path
python pdf_to_images.py --pdf /path/to/your/document.pdf

# Specify output directory and threads
python pdf_to_images.py --pdf /path/to/your/document.pdf --output custom_images_dir --threads 8
```

You can also set these values in your `.env` file:
```
PDF_PATH=/path/to/your/document.pdf
OUTPUT_DIR=custom_images_dir
IMAGE_THREADS=8
```

### 2. Extract Entities
Process the images using GPT-4 Vision to extract structured compliance entities:

```bash
# Process all pages
python entity_extractor.py

# Process a specific number of pages
python entity_extractor.py 10
```

This will save extracted entities as JSON files in the `extracted_entities` directory.

### 3. Load Imperium Rules
Load existing Imperium rules into the Neo4j database:

```bash
# Use default settings (looks for Excel file at ~/Downloads/Rules.xlsx)
python process_rules_imperium.py

# Specify a custom Excel path
python process_rules_imperium.py --excel /path/to/your/Rules.xlsx

# Control batch size and limit the number of rules to process
python process_rules_imperium.py --batch-size 50 --limit 1000

# Dry run - just load Excel file and count rules without processing
python process_rules_imperium.py --dry-run
```

You can also set these values in your `.env` file:
```
RULES_EXCEL_PATH=/path/to/your/Rules.xlsx
BATCH_SIZE=50
```

### 4. Load Extracted Entities to Graph
Load the extracted entities into the Neo4j graph database, connecting to existing Imperium rules:

```bash
python compliance_graph_loader.py
```

### 5. Query the Graph
Use the Cypher queries in `experimental/cypher_queries.md` to explore and analyze the knowledge graph.

## Key Files

- **entity_extractor.py**: Main script for extracting entities from images
- **entity_extraction_prompt.txt**: Prompt for GPT-4 Vision with extraction instructions
- **toc_extraction_prompt.txt**: Specialized prompt for Table of Contents pages
- **pdf_to_images.py**: Converts PDF to images for processing
- **compliance_graph_loader.py**: Loads extracted entities into Neo4j
- **process_rules_imperium.py**: Loads Imperium rules from Excel into Neo4j
- **entity_context_manager.py**: Manages entity context across multiple pages
- **clear_graph.py**: Utility to reset the Neo4j database
- **query_graph.py**: Script to run queries against the graph database
- **graph_db/**: Database interface implementations

## Configuration

Adjust settings in `config.json`:
```json
{
  "api_model": "gpt-4-vision-preview",
  "image_threads": 6,
  "gpt4_threads": 3
}
```

## Testing and Verification

The `experimental` directory contains various tools for testing and verification:
- **cypher_queries.md**: Useful Cypher queries for exploring the graph
- **graph_stats.py**: Generates statistics about the graph
- **check_rule_ids.py**: Verifies rule ID connections
- **test_extraction.py**: Tests entity extraction on a single page

## Troubleshooting

- **API Key Issues**: Ensure your OpenAI API key is set correctly in the `.env` file
- **Neo4j Connection**: Verify Neo4j is running and credentials are correct
- **Missing Rule IDs**: Use the experimental scripts to verify rule connections
- **JSON Parsing Errors**: Check extracted JSON files for formatting issues

## Advanced Usage

### Hybrid TOC Processing Architecture

The system implements a sophisticated approach to handle Table of Contents (TOC) pages in compliance documents:

#### Page Type Detection
- The `is_table_of_contents()` function sends small API requests to analyze each page
- It identifies three distinct page types:
  - **FULL_TOC**: Pages that primarily contain a Table of Contents
  - **HYBRID**: Pages with both TOC elements and detailed content
  - **REGULAR**: Standard content pages with no TOC elements

#### Dual-Extraction Process
For TOC and hybrid pages, the system employs a specialized prompt that:
1. Extracts the main category and ALL subcategories from TOC sections
2. Simultaneously processes any detailed content using the same extraction rules as regular pages
3. Ensures entities are created exactly once (no duplication if a subcategory appears in TOC and detailed sections)

#### Benefits of the Hybrid Approach
- **Early Structure Construction**: Builds a comprehensive skeleton of categories/subcategories from the beginning
- **Context Enrichment**: Provides rich context for subsequent pages that may not explicitly mention parent categories
- **Flexible Document Handling**: Works with documents that interleave TOC elements with detailed content
- **Enhanced Entity Relationships**: Ensures guidelines and rules connect to the correct subcategories in the hierarchy

#### Implementation Details
TOC processing is implemented through:
- A dedicated TOC detection function in `entity_extractor.py`
- A specialized `toc_extraction_prompt.txt` optimized for extracting both TOC structure and detailed content
- Special handling of hybrid pages with both TOC elements and detailed content

### Batch Processing
For large PDFs, process in batches:
```bash
export NUM_FILES=10
python entity_extractor.py
```

### Custom Categories
To enforce a specific primary category:
```bash
# Edit entity_context_manager.py to set a primary category
# In the initialize_context method:
self.entity_context['offensive_content_category']['Your Primary Category'] = {
    'is_primary': True
}
```

### Manual Rule Connections
Connect guidelines to Imperium rules manually:
```bash
# Edit experimental/connect_guidelines_to_rules.py with your rule IDs
python experimental/connect_guidelines_to_rules.py
```

## License
[Insert your license information here]

## Contributors
[List contributors here]