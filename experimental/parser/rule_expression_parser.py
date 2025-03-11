import os
import json
import pandas as pd
import re
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up paths
RULES_EXCEL_PATH = os.path.expanduser("~/Downloads/Rules.xlsx")
OUTPUT_DIR = "parsed_rules"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GPT-4 prompt template for parsing rule expressions
PROMPT_TEMPLATE = """
You are an expert in parsing complex logical expressions into graph structures. Your task is to analyze the following Imperium rule expression and convert it into a structured JSON format that represents its logical structure for import into a graph database.

Rule Expression: {rule_expression}

# INSTRUCTIONS:

1. Parse the rule expression into a hierarchical JSON structure that preserves all logical operations (AND, OR), comparisons, fields, operators, and values.

2. Follow these parsing rules:
   - Parentheses indicate nesting levels in the expression
   - Field names appear in UPPERCASE (like TITLE, BRAND, CATEGORY)
   - Operators include: CONTAINS, EQUALS, NOT_CONTAINS, NOT_EQUALS
   - Commas separate multiple values for a single comparison
   - Boolean operators AND and OR connect conditions

3. Create a structured JSON with these node types:
   - LogicalNode: Represents AND/OR operations with child conditions
   - ComparisonNode: Represents field comparisons with operator and values

4. For each comparison, extract:
   - Field: The attribute being checked (TITLE, BRAND, etc.)
   - Operator: The comparison type (CONTAINS, EQUALS, etc.)
   - Values: Array of values being compared, splitting comma-separated lists

# OUTPUT FORMAT:

The output should be valid JSON with this structure:
```json
{{
  "type": "LOGICAL",
  "operator": "AND|OR",
  "conditions": [
    {{
      "type": "COMPARISON",
      "field": "FIELD_NAME",
      "operator": "COMPARISON_OPERATOR",
      "values": ["value1", "value2", ...]
    }},
    {{
      "type": "LOGICAL",
      "operator": "AND|OR",
      "conditions": [...]
    }}
  ]
}}
```

Important notes:
1. Ensure all parentheses are properly balanced in your analysis
2. Preserve the exact hierarchical structure of the expression
3. Split comma-separated values into separate array items
4. Verify that your output is valid JSON that can be parsed programmatically
5. Handle edge cases like empty expressions or malformed expressions gracefully

DO NOT include any explanation, just return the JSON.
"""

def parse_rule_expression(rule_id, rule_expression):
    """
    Send rule expression to GPT-4 for parsing into structured JSON
    
    Args:
        rule_id: The ID of the rule being parsed
        rule_expression: The rule expression to parse
    
    Returns:
        Parsed JSON structure of the rule expression
    """
    try:
        # Prepare the prompt with the rule expression
        prompt = PROMPT_TEMPLATE.format(rule_expression=rule_expression)
        
        # Call GPT-4 to parse the expression
        response = client.chat.completions.create(
            model="gpt-4-turbo",  # Use the appropriate model here
            messages=[
                {"role": "system", "content": "You are a precise logical expression parser."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,  # Use low temperature for consistent parsing
            max_tokens=4000
        )
        
        # Extract the parsed JSON from the response
        parsed_content = response.choices[0].message.content.strip()
        
        # Remove any markdown code blocks if present
        parsed_content = re.sub(r'```json', '', parsed_content)
        parsed_content = re.sub(r'```', '', parsed_content)
        
        # Parse JSON to validate structure
        parsed_json = json.loads(parsed_content.strip())
        
        return parsed_json
    
    except Exception as e:
        print(f"Error parsing rule {rule_id}: {e}")
        return {"error": str(e), "rule_id": rule_id}

def generate_rule_json(rule_row):
    """
    Generate a complete JSON representation of a rule including metadata and parsed expression
    
    Args:
        rule_row: A pandas Series containing a single rule's data
    
    Returns:
        Complete JSON representation of the rule
    """
    try:
        # Extract basic rule metadata
        rule_metadata = {
            "rule_id": int(rule_row["Rule_Id"]),
            "rule_name": rule_row["Rule_Name"],
            "rule_description": rule_row["Rule_Description"],
            "rule_version": int(rule_row["Rule_Version"]),
            "start_date": rule_row["Start_Date"].strftime("%Y-%m-%d"),
            "end_date": rule_row["End_Date"].strftime("%Y-%m-%d"),
            "rule_status": rule_row["Rule_Status"],
            "global_filter": rule_row["Global_Filter"],
            "local_filter": rule_row["Local_Filter"],
            "policy_name": rule_row["PolicyName"],
            "policy_group": rule_row["PolicyGroup"],
            "rule_priority": rule_row["RulePriority"],
            "rule_type": rule_row["RuleType"],
            "action": rule_row["Action"],
            "reason_code": rule_row["Reason Code"]
        }
        
        # Parse the rule expression
        rule_expression = str(rule_row["Rule_Expression"])
        rule_id = rule_row["Rule_Id"]
        
        parsed_expression = parse_rule_expression(rule_id, rule_expression)
        
        # Combine metadata with parsed expression
        full_rule_json = {
            "rule_metadata": rule_metadata,
            "expression_tree": parsed_expression
        }
        
        return full_rule_json
    
    except Exception as e:
        print(f"Error generating JSON for rule {rule_row['Rule_Id']}: {e}")
        return {"error": str(e), "rule_id": rule_row["Rule_Id"]}

def save_rule_json(rule_json, rule_id):
    """
    Save rule JSON to file
    
    Args:
        rule_json: The JSON data to save
        rule_id: The ID of the rule
    """
    filename = os.path.join(OUTPUT_DIR, f"rule_{rule_id}.json")
    with open(filename, 'w') as f:
        json.dump(rule_json, f, indent=2)
    print(f"Saved rule {rule_id} to {filename}")

def process_sample_rules(num_rules=5, excel_path=None):
    """
    Process a sample of rules from the Excel file and verify parsing
    
    Args:
        num_rules: Number of rules to process in the sample (None for all)
        excel_path: Path to the Excel file (defaults to RULES_EXCEL_PATH)
    
    Returns:
        Number of successfully parsed rules
    """
    try:
        # Use provided excel path or default
        excel_path = excel_path or RULES_EXCEL_PATH
        
        # Load rules from Excel
        print(f"Loading rules from {excel_path}")
        df = pd.read_excel(excel_path)
        
        # Determine how many rules to process
        total_rules = len(df)
        rules_to_process = total_rules if num_rules is None else min(num_rules, total_rules)
        
        print(f"Loaded {total_rules} rules from Excel. Processing {rules_to_process} rules...")
        
        # Select rules to process
        if rules_to_process == total_rules:
            # Process all rules
            rules_to_process_df = df
        else:
            # Select rules with varying complexity
            sorted_by_expr_len = df.copy()
            sorted_by_expr_len['expr_len'] = sorted_by_expr_len['Rule_Expression'].astype(str).apply(len)
            sorted_by_expr_len = sorted_by_expr_len.sort_values('expr_len')
            
            # Get sample from different quantiles
            indices = []
            for i in range(rules_to_process):
                idx = int(i * total_rules / rules_to_process)
                indices.append(idx)
            
            rules_to_process_df = sorted_by_expr_len.iloc[indices]
        
        success_count = 0
        
        # Process each rule
        for idx, rule in enumerate(rules_to_process_df.iterrows()):
            _, rule_data = rule
            rule_id = rule_data["Rule_Id"]
            print(f"\nProcessing rule {rule_id} ({idx+1}/{rules_to_process}): {rule_data['Rule_Name']}")
            print(f"Expression length: {len(str(rule_data['Rule_Expression']))} characters")
            
            # Generate rule JSON
            start_time = time.time()
            rule_json = generate_rule_json(rule_data)
            elapsed_time = time.time() - start_time
            
            # Check if parsing was successful
            if "error" in rule_json:
                print(f"❌ Failed to parse rule {rule_id}: {rule_json['error']}")
            else:
                print(f"✅ Successfully parsed rule {rule_id} in {elapsed_time:.2f} seconds")
                success_count += 1
                
                # Save the rule JSON
                save_rule_json(rule_json, rule_id)
        
        # Report success rate
        success_rate = success_count / rules_to_process * 100
        print(f"\nSuccessfully parsed {success_count}/{rules_to_process} rules ({success_rate:.1f}%)")
        return success_count
        
    except Exception as e:
        print(f"Error processing rules: {e}")
        return 0

def main():
    """
    Main function to run the rule parser
    """
    # Process a sample of rules to verify parsing
    process_sample_rules(num_rules=5)
    
    print("\nRule parsing verification complete")

if __name__ == "__main__":
    main()