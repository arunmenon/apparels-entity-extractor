# Agentic Workflow Reporting Tools

This directory contains reporting tools for analyzing and evaluating the agentic workflow for entity extraction.

## Available Tools

### 1. Extraction Report

Generates summary and detailed reports of extracted entities across pages.

```bash
python extraction_report.py --pages page_1_toc page_1_details page_2 page_3
```

**Features:**
- Summarizes categories, subcategories, guidelines, and rules per page
- Provides detailed listing of all extracted entities
- Saves reports in CSV and JSON formats

### 2. TOC Evaluation

Evaluates Table of Contents extraction against ground truth using fuzzy matching.

```bash
python toc_evaluation.py --extracted extracted_entities/extracted_page_1_toc.json --ground-truth ground_truth_subcategories.json
```

**Features:**
- Calculates precision, recall, and F1 scores
- Identifies matched, missing, and hallucinated categories
- Adjustable fuzzy matching threshold

### 3. Context Analysis

Analyzes entity relationships and context maintenance across pages.

```bash
python context_analysis.py --pages page_1_toc page_1_details page_2 page_3
```

**Features:**
- Identifies entities spanning multiple pages
- Traces cross-page relationships
- Visualizes entity graph with category-subcategory hierarchies
- Maps rules and guidelines to their parent categories

## Output Directory

All reports and visualizations are saved to `experimental/reporting/outputs/`.

## Usage for Multi-Page Analysis

To run a complete analysis of the first 10 pages:

```bash
# Generate extraction report
python extraction_report.py --pages page_1_toc page_1_details page_2 page_3 page_4 page_5 page_6 page_7 page_8 page_9 page_10

# Evaluate TOC extraction
python toc_evaluation.py --extracted extracted_entities/extracted_page_1_toc.json --ground-truth ground_truth_subcategories.json

# Analyze context relationships
python context_analysis.py --pages page_1_toc page_1_details page_2 page_3 page_4 page_5
```

## Key Findings

Based on initial analysis:

1. TOC extraction achieves varying precision and recall depending on the formatting
2. The context manager successfully maintains relationships across pages
3. Cross-page relationships show how subcategories and rules are connected
4. The workflow effectively handles hybrid pages with both TOC and detail content