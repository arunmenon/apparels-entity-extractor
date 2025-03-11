import os
import json
import sys

# Test rule expression
TEST_EXPRESSION = """
( (TITLE CONTAINS keyword1,keyword2 OR BRAND EQUALS brand1) AND CATEGORY NOT_EQUALS category1 )
"""

# Mock response that would come from GPT-4
MOCK_PARSED_RESPONSE = {
    "type": "LOGICAL",
    "operator": "AND",
    "conditions": [
        {
            "type": "LOGICAL",
            "operator": "OR",
            "conditions": [
                {
                    "type": "COMPARISON",
                    "field": "TITLE",
                    "operator": "CONTAINS",
                    "values": ["keyword1", "keyword2"]
                },
                {
                    "type": "COMPARISON",
                    "field": "BRAND",
                    "operator": "EQUALS",
                    "values": ["brand1"]
                }
            ]
        },
        {
            "type": "COMPARISON",
            "field": "CATEGORY",
            "operator": "NOT_EQUALS",
            "values": ["category1"]
        }
    ]
}

def mock_generate_rule_json(rule_data):
    """
    Generate a mock rule JSON similar to what would be created in the real flow
    """
    # Create mock rule metadata
    rule_metadata = {
        "rule_id": 12345,
        "rule_name": "Test Rule",
        "rule_description": "A test rule for demonstration",
        "rule_version": 1,
        "start_date": "2023-01-01",
        "end_date": "2099-12-31",
        "rule_status": "Active",
        "global_filter": "TestFilter",
        "local_filter": "",
        "policy_name": "Test Policy",
        "policy_group": "Test Group",
        "rule_priority": "P9",
        "rule_type": "Text",
        "action": "Block",
        "reason_code": "Test Reason"
    }
    
    # Combine metadata with parsed expression
    return {
        "rule_metadata": rule_metadata,
        "expression_tree": MOCK_PARSED_RESPONSE
    }

def main():
    """
    Test rule parsing with a mock response
    """
    print("Testing rule parser with a mock response...")
    
    try:
        # Generate mock rule JSON
        rule_json = mock_generate_rule_json({})
        
        # Create parsed_rules directory if it doesn't exist
        os.makedirs("parsed_rules", exist_ok=True)
        
        # Save mock rule JSON to file
        output_path = "parsed_rules/rule_12345.json"
        with open(output_path, "w") as f:
            json.dump(rule_json, f, indent=2)
        
        print(f"✅ Successfully created mock rule JSON file at {output_path}")
        print("\nMock rule JSON:")
        print(json.dumps(rule_json, indent=2))
        
        print("\nNext steps:")
        print("1. Run 'python process_imperium_rules.py --load --num-rules 1' to load the mock rule")
        print("2. This will demonstrate the graph schema structure using the mock data")
        
        return 0
    
    except Exception as e:
        print(f"❌ Error in test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())