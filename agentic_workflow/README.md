# Agentic Workflow for Entity Extraction

This module implements a modular, agentic workflow for extracting structured entities from compliance documents. Each agent in the workflow has a focused responsibility, making the system more maintainable and easier to debug.

## Architecture

The workflow employs several design patterns:

1. **Factory Pattern**: Agents are created via a factory that manages instantiation
2. **Strategy Pattern**: Different extraction techniques can be swapped
3. **Chain of Responsibility**: Agents form a processing pipeline
4. **Template Method**: Common processing steps with customizable hooks
5. **Observer Pattern**: Hook system for workflow extensions

### Core Agents

1. **PageClassifierAgent**: Classifies pages as `FULL_TOC`, `HYBRID`, or `REGULAR`.
   - Input: Single page image
   - Output: Classification result
   - File: `page_classifier.py`

2. **EntityExtractorAgent**: Extracts structured entity data from pages.
   - Input: Page classification + page image
   - Output: Structured JSON with categories, subcategories, rules, etc.
   - File: `entity_extractor.py`

3. **ContextAgent**: Manages context and relationships between entities.
   - Input: Extracted JSON from EntityExtractorAgent
   - Output: Updated global context
   - File: `context_agent.py`

4. **CypherGeneratorAgent**: Generates Neo4j Cypher queries using LLM.
   - Input: Entity context (final or per-page)
   - Output: Valid Cypher query for Neo4j
   - File: `cypher_generator.py`

The `AgentWorkflow` class in `agent_workflow.py` orchestrates these agents, managing the overall process flow.

## Configuration

The workflow is configured via `config.json`:

```json
{
  "api_model": "gpt-4o",
  "gpt4_threads": 3,
  "agent_pipeline": ["classifier", "extractor", "context", "cypher"],
  "first_page_serial": true,
  "toc_page_index": 0
}
```

Key configuration options:
- `agent_pipeline`: List of agents to run in order
- `first_page_serial`: Process first/TOC page serially before parallel processing
- `toc_page_index`: Which page contains the TOC (default is 0, the first page)

## Usage

You can run the workflow using the provided script:

```bash
# Basic usage
python run_agentic_workflow.py

# With options
python run_agentic_workflow.py --sequential --limit 10
```

Optional arguments:
- `--limit N`: Process only the first N pages
- `--sequential`: Process pages sequentially (default is parallel)
- `--config PATH`: Specify a custom config file
- `--images-dir DIR`: Specify a custom image directory

## Creating Custom Agents

You can extend the workflow by creating custom agents:

```python
from agentic_workflow.agent_workflow import AgentWorkflow

# Create a custom agent
class MyCustomAgent:
    def __init__(self, config=None):
        self.config = config or {}
    
    def process_data(self, data, context):
        # Custom processing logic
        return processed_result

# Register with the workflow
workflow = AgentWorkflow()
workflow.register_agent('custom', MyCustomAgent())
```

## Special Features

### TOC Processing

The workflow can handle Table of Contents (TOC) pages specially:

1. TOC pages are identified by the PageClassifierAgent
2. Different prompts are used for TOC vs regular pages
3. The first page (typically TOC) can be processed serially to establish primary categories before parallel processing begins

### LLM-based Cypher Generation

Instead of procedural Cypher generation, the workflow uses an LLM to generate optimized Cypher queries based on the extracted entities. This provides more flexibility and can handle complex entity relationships.

## Output

The workflow produces:
- `extracted_entities/`: JSON files with structured data from each page
- `incremental_cypher/`: Incremental Cypher queries for each page
- `final_cypher.json`: Comprehensive Cypher query for the entire document
- `compliance_context.json`: The consolidated entity context

## Benefits

- **Separation of Concerns**: Each agent focuses on one task
- **Improved Error Handling**: Issues in one agent don't affect others
- **LLM-optimized Queries**: Better Cypher generation with fewer hallucinations
- **Configurable Processing**: Flexible pipeline with serial/parallel options
- **Extensibility**: Easy to add custom agents or modify existing ones