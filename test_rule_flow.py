import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """
    Driver script for testing the rule flow with mock data
    """
    print("Testing Imperium Rule Flow with Mock Data")
    print("========================================")
    
    # Step 1: Ensure the parsed_rules directory exists
    os.makedirs("parsed_rules", exist_ok=True)
    
    # Step 2: Generate mock rule data
    print("\nStep 1: Generating mock rule data...")
    try:
        # Import and run the mock test
        print("Running test_rule_parser_mock.py")
        from test_rule_parser_mock import main as mock_main
        result = mock_main()
        if result != 0:
            print("Error: Failed to generate mock rule data")
            return 1
    except Exception as e:
        print(f"Error generating mock data: {e}")
        return 1
    
    # Step 3: Load the rules into the graph (in mock mode)
    print("\nStep 2: Loading mock rule data into graph...")
    try:
        # Set mock mode in environment
        os.environ["NEO4J_URI"] = "mock"
        
        # Import and run the rule graph loader
        from rule_graph_loader import load_rules_into_graph
        success_count = load_rules_into_graph(num_rules=1)
        
        if success_count == 0:
            print("Error: Failed to load any rules")
            return 1
    except Exception as e:
        print(f"Error loading rules into graph: {e}")
        return 1
    
    print("\nTest complete! The rule flow is working correctly.")
    print("To enable the full implementation, edit process_imperium_rules.py and uncomment the code.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())