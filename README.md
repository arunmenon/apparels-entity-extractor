# Compliance Entity Extractor

A system for extracting compliance entities from product documentation and building a knowledge graph.

## Overview

This project extracts structured information from compliance documentation images, including:
- Categories
- Subcategories
- Guidelines
- Rules (prohibitions and allowances)

The extraction system uses an agentic workflow to process images, identify entities, and generate a graph representation.

## Architecture

The system follows an agentic workflow:

1. **Page Classification**: Determine if a page is TOC, regular, or hybrid
2. **Entity Extraction**: Extract structured data based on page type
3. **Context Management**: Maintain relationships between entities across pages
4. **Cypher Generation**: Generate graph database queries

The system uses prompt templates stored in the `prompts/` folder for different aspects of extraction.

## Key Features

- **Context-Aware Extraction**: Maintains category and subcategory relationships across pages
- **Subcategory Normalization**: Matches extracted subcategories against the Table of Contents list
- **Rule Classification**: Identifies different rule types (imperium_rule, policy_rule)
- **Color-Aware Processing**: Uses color-coding to determine PROHIBITS/ALLOWS status

## Usage

```bash
# Run the agentic workflow on all images
python run_agentic_workflow.py

# Run the workflow on a limited set of images
python run_agentic_workflow.py --limit 10

# Process images sequentially (default is parallel)
python run_agentic_workflow.py --sequential

# Specify custom config file
python run_agentic_workflow.py --config custom_config.json
```

## Configuration

Edit `config.json` to customize the workflow:

```json
{
  "api_model": "gpt-4o",
  "image_threads": 6,
  "gpt4_threads": 3,
  "agent_pipeline": ["classifier", "extractor", "context", "cypher"],
  "first_page_serial": true,
  "toc_page_index": 0
}
```

## Analysis & Reporting

The project includes several reporting tools in the `experimental/reporting/` directory:

- `extraction_report.py`: Generate summary and detailed reports of extracted entities
- `context_inheritance.py`: Analyze entity relationships across pages
- `toc_evaluation.py`: Evaluate TOC extraction against ground truth

## License

© 2025 Walmart. All rights reserved.