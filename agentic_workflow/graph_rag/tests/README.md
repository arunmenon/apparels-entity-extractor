# Graph RAG Test Suite

This directory contains tests for the Graph RAG module components, designed to verify that all parts of the workflow function correctly and that no steps are being bypassed.

## Test Components

### 1. End-to-End Testing
- `test_graph_rag_direct.py`: Tests the complete end-to-end RAG workflow from question to answer
  - Verifies that the entire pipeline works correctly
  - Tests with a variety of question types

### 2. Component Testing
- `test_query_decomposition.py`: Tests the query decomposition component in isolation
  - Verifies proper schema retrieval
  - Confirms LLM-based query generation with appropriate Cypher syntax
  
- `test_graph_retriever.py`: Tests the graph retrieval component in isolation
  - Verifies database connection
  - Tests execution of various types of Cypher queries
  - Validates result formatting
  
- `test_reasoning_agent.py`: Tests the reasoning component in isolation
  - Verifies appropriate answers based on retrieved context
  - Tests reasoning with various scenarios (results, no results, errors)
  - Validates evidence citation and confidence scoring

### 3. Run All Tests
- `run_all_tests.py`: Runs all test scripts and collects results
  - Creates timestamped test runs
  - Provides summaries and detailed logs

## Usage

### Running Individual Tests

To run a specific test:

```bash
python test_query_decomposition.py
```

To test with a specific question:

```bash
python test_query_decomposition.py "What compliance areas exist in the system?"
```

### Running All Tests

To run the full test suite:

```bash
python run_all_tests.py
```

Test results are saved to the `test_results` directory by default. You can specify a different output directory:

```bash
python run_all_tests.py custom_results_dir
```

## Test Output

Each test script produces:
- JSON output file with test results
- Detailed logging during execution

The `run_all_tests.py` script produces:
- A summary JSON file with results from all tests
- Individual test outputs
- stdout and stderr logs for each test
- Test run summary in the console

## Verification Approach

These tests verify that:

1. The **schema information** is correctly retrieved from the database
2. The **query decomposition** process correctly generates Cypher queries targeting the right entities
3. The **graph retrieval** process correctly executes queries and formats results
4. The **reasoning** process correctly analyzes retrieved data to generate answers
5. The **full workflow** functions correctly from question to answer

This approach avoids the problem of "bypassing" the RAG workflow by ensuring each component is tested both in isolation and as part of the complete flow.