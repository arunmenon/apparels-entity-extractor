import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    """
    Main entry point for processing Imperium rules
    """
    parser = argparse.ArgumentParser(description="Process Imperium rules from Excel file into graph database")
    parser.add_argument("--parse", action="store_true", help="Parse rule expressions from Excel file")
    parser.add_argument("--load", action="store_true", help="Load parsed rules into graph database")
    parser.add_argument("--all", action="store_true", help="Run complete workflow: parse and load")
    parser.add_argument("--num-rules", type=int, default=10, help="Number of rules to process (default: 10, 0 for all)")
    parser.add_argument("--excel-path", type=str, default=os.path.expanduser("~/Downloads/Rules.xlsx"), 
                         help="Path to the Rules.xlsx file")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode without real database")
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not (args.parse or args.load or args.all):
        parser.print_help()
        return 1
    
    # Check if excel file exists for parsing
    if (args.parse or args.all) and not os.path.exists(args.excel_path):
        print(f"Error: Excel file not found at {args.excel_path}")
        return 1
    
    # Set number of rules to process
    num_rules = None if args.num_rules == 0 else args.num_rules
    
    # Set mock mode if requested
    if args.mock:
        print("Running in MOCK mode - database operations will be simulated")
        os.environ["NEO4J_URI"] = "mock"
    
    # Run complete workflow or individual steps
    if args.all or args.parse:
        print(f"\n{'='*80}\nParsing rule expressions\n{'='*80}")
        
        # Use mock data if in mock mode and not parsing explicitly
        if args.mock and not args.parse:
            print("Using mock rule data...")
            from test_rule_parser_mock import main as generate_mock
            generate_mock()
        else:
            # Use the real parser with OpenAI
            from rule_expression_parser import process_sample_rules
            success_count = process_sample_rules(num_rules=num_rules, excel_path=args.excel_path)
            
            if success_count == 0:
                print("Error: Failed to parse any rules")
                return 1
    
    if args.all or args.load:
        print(f"\n{'='*80}\nLoading rules into graph database\n{'='*80}")
        # Check if parsed rules directory exists
        parsed_rules_dir = os.getenv("PARSED_RULES_DIR", "parsed_rules")
        if not os.path.exists(parsed_rules_dir):
            print(f"Error: Parsed rules directory '{parsed_rules_dir}' does not exist")
            print("Please run with --parse first to generate parsed rules")
            return 1
        
        # Check if the directory is empty
        rule_files = [f for f in os.listdir(parsed_rules_dir) if f.endswith('.json')]
        if not rule_files:
            print(f"Error: No parsed rule files found in '{parsed_rules_dir}'")
            return 1
            
        from rule_graph_loader import load_rules_into_graph
        load_rules_into_graph(num_rules=num_rules)
    
    print("\nImperium rules processing completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())