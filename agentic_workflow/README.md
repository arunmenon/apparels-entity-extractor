# Agentic Workflow for Compliance Document Processing

This module implements a modular, agentic workflow for extracting structured data from compliance documents. Each agent in the workflow has a focused responsibility, making the system more maintainable and easier to debug.

## Architecture

The workflow consists of four primary agents:

1. **PageClassifierAgent**: Classifies pages as `FULL_TOC`, `HYBRID`, or `REGULAR`.
   - Input: Single page image
   - Output: Classification result
   - File: `page_classifier.py`

2. **EntityExtractorAgent**: Extracts structured entity data from pages.
   - Input: Page classification + page image
   - Output: Structured data (JSON) with categories, subcategories, rules, etc.
   - File: `entity_extractor.py`

3. **ContextAgent**: Manages context and relationships between entities.
   - Input: Extracted JSON from EntityExtractorAgent
   - Output: Updated global context
   - File: `context_agent.py`

4. **CypherGeneratorAgent**: Generates Neo4j Cypher queries.
   - Input: Entity context (final or per-page)
   - Output: Valid Cypher query for Neo4j
   - File: `cypher_generator.py`

The `AgentWorkflow` class in `agent_workflow.py` orchestrates these agents, managing the overall process flow.

## Usage

You can run the workflow in two modes:

1. **Sequential Processing**:
   ```
   python agent_workflow.py --sequential
   ```

2. **Parallel Processing** (default):
   ```
   python agent_workflow.py
   ```

Optional arguments:
- `--limit N`: Process only the first N pages
- `--sequential`: Process pages sequentially (default is parallel)

## Output

The workflow produces:
- `extracted_entities/`: JSON files with structured data from each page
- `incremental_cypher/`: Incremental Cypher queries for each page
- `final_cypher.json`: Comprehensive Cypher query for the entire document
- `compliance_context.json`: The consolidated entity context

## Benefits

- **Modularity**: Each agent has a single responsibility
- **Maintainability**: Easy to debug and enhance individual components
- **Flexibility**: Can run in batch or incremental mode
- **Scalability**: Parallel processing of classification and extraction
- **Reusability**: Agents can be used independently for other tasks