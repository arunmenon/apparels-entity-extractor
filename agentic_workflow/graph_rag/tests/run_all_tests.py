#!/usr/bin/env python3
"""
Run All Graph RAG Tests

This script runs all the test scripts for the Graph RAG components:
1. Query Decomposition Tests
2. Graph Retriever Tests  
3. Reasoning Agent Tests
4. Full GraphRAG End-to-End Tests

Output is saved to test_results directory.
"""

import os
import sys
import logging
import time
import subprocess
import datetime

# Fix import paths when running from any location
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_all_tests(output_dir="test_results"):
    """
    Run all the test scripts for Graph RAG components.
    
    Args:
        output_dir: Directory to save test results
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get the current directory (where this script is located)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define test scripts to run
    test_scripts = [
        "test_query_decomposition.py",
        "test_graph_retriever.py",
        "test_reasoning_agent.py",
        "test_graph_rag_direct.py"
    ]
    
    # Get timestamp for this test run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Log file for this run
    log_file = os.path.join(output_dir, f"test_run_{timestamp}.log")
    
    logger.info(f"Starting test run {timestamp}")
    logger.info(f"Log file: {log_file}")
    
    # Run each test script
    results = []
    for script in test_scripts:
        script_path = os.path.join(script_dir, script)
        script_name = os.path.basename(script)
        script_output = os.path.join(output_dir, f"{script_name.replace('.py', '')}_{timestamp}.json")
        
        logger.info(f"Running {script_name}...")
        
        # Set environment variable for the output file
        env = os.environ.copy()
        
        # Construct command
        cmd = [sys.executable, script_path]
        
        try:
            # Run the script
            start_time = time.time()
            process = subprocess.run(
                cmd, 
                env=env,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            end_time = time.time()
            
            # Log the output
            logger.info(f"{script_name} completed in {end_time - start_time:.2f} seconds")
            
            # Save stdout and stderr
            with open(f"{script_output}.stdout", "w") as f:
                f.write(process.stdout)
            
            with open(f"{script_output}.stderr", "w") as f:
                f.write(process.stderr)
            
            results.append({
                "script": script_name,
                "success": True,
                "runtime": end_time - start_time,
                "stdout": f"{script_output}.stdout",
                "stderr": f"{script_output}.stderr",
                "output": script_output
            })
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running {script_name}: {e}")
            
            # Save stdout and stderr even on error
            with open(f"{script_output}.stdout", "w") as f:
                f.write(e.stdout)
            
            with open(f"{script_output}.stderr", "w") as f:
                f.write(e.stderr)
            
            results.append({
                "script": script_name,
                "success": False,
                "error": str(e),
                "stdout": f"{script_output}.stdout",
                "stderr": f"{script_output}.stderr",
                "output": script_output
            })
    
    # Write summary
    summary_file = os.path.join(output_dir, f"test_summary_{timestamp}.json")
    with open(summary_file, "w") as f:
        import json
        json.dump({
            "timestamp": timestamp,
            "results": results
        }, f, indent=2)
    
    # Log summary
    logger.info(f"Test run completed. Summary saved to {summary_file}")
    logger.info("Test Results:")
    for result in results:
        status = "SUCCESS" if result["success"] else "FAILURE"
        logger.info(f"{result['script']}: {status}")
    
    return results

if __name__ == "__main__":
    import sys
    
    # Get output directory from command line if provided
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "test_results"
    
    # Run all tests
    run_all_tests(output_dir)