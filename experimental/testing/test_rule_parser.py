import os
import sys
from rule_expression_parser import parse_rule_expression

# Test rule expression
TEST_EXPRESSION = """
( (TITLE CONTAINS keyword1,keyword2 OR BRAND EQUALS brand1) AND CATEGORY NOT_EQUALS category1 )
"""

def main():
    """
    Test the rule parser with a simple expression
    """
    # Check if OPENAI_API_KEY is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set the environment variable or create a .env file with your OpenAI API key.")
        return 1
    
    print("Testing rule parser with simple expression...")
    
    try:
        # Parse test expression
        parsed = parse_rule_expression("test", TEST_EXPRESSION)
        
        # Check if parsing was successful
        if "error" in parsed:
            print(f"❌ Parsing failed: {parsed['error']}")
            return 1
        
        # Print parsed expression
        print("✅ Successfully parsed test expression!")
        print("Parsed result:")
        import json
        print(json.dumps(parsed, indent=2))
        return 0
    
    except Exception as e:
        print(f"❌ Error testing rule parser: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())