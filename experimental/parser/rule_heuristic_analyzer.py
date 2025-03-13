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
OUTPUT_DIR = "parsed_rule_heuristics"
PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                          "prompts", "rule_heuristic_extraction_prompt.txt")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load GPT-4 prompt template from external file
with open(PROMPT_PATH, 'r') as f:
    PROMPT_TEMPLATE = f.read()

def analyze_rule_expression(rule_id, rule_expression, rule_name=None, policy_name=None):
    """
    Send rule expression to GPT-4 for high-level analysis
    
    Args:
        rule_id: The ID of the rule being analyzed
        rule_expression: The rule expression to analyze
        rule_name: The name of the rule (for context)
        policy_name: The policy name (for context)
    
    Returns:
        High-level analysis of the rule expression as JSON
    """
    try:
        # Prepare the prompt with the rule expression
        prompt = PROMPT_TEMPLATE.format(rule_expression=rule_expression)
        
        # Add rule name and policy as system context if available
        system_content = "You are a precise rule analyzer for compliance systems."
        if rule_name or policy_name:
            context = []
            if rule_name:
                context.append(f"Rule Name: {rule_name}")
            if policy_name:
                context.append(f"Policy: {policy_name}")
            if context:
                system_content += f" Analyzing: {' - '.join(context)}"
        
        # Call GPT-4o to analyze the expression
        response = client.chat.completions.create(
            model="gpt-4o",  # Using GPT-4o as requested
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Use low temperature for consistent analysis
            max_tokens=2000
        )
        
        # Extract the analysis from the response
        analyzed_content = response.choices[0].message.content.strip()
        
        # Remove any markdown code blocks if present
        analyzed_content = re.sub(r'```json', '', analyzed_content)
        analyzed_content = re.sub(r'```', '', analyzed_content)
        
        # Parse JSON to validate structure
        analyzed_json = json.loads(analyzed_content.strip())
        
        return analyzed_json
    
    except Exception as e:
        print(f"Error analyzing rule {rule_id}: {e}")
        return {
            "error": str(e), 
            "rule_id": rule_id,
            "rule_intent": "Error during analysis"
        }

def generate_rule_heuristic_json(rule_row):
    """
    Generate a complete JSON representation of a rule with high-level analysis
    
    Args:
        rule_row: A pandas Series containing a single rule's data
    
    Returns:
        Complete JSON representation of the rule with heuristic analysis
    """
    try:
        # Extract basic rule metadata
        rule_metadata = {
            "rule_id": int(rule_row["Rule_Id"]),
            "rule_name": rule_row["Rule_Name"],
            "rule_description": rule_row["Rule_Description"],
            "policy_name": rule_row["PolicyName"],
            "policy_group": rule_row["PolicyGroup"],
            "rule_priority": rule_row["RulePriority"],
            "rule_type": rule_row["RuleType"],
        }
        
        # Get the rule expression
        rule_expression = str(rule_row["Rule_Expression"])
        rule_id = rule_row["Rule_Id"]
        rule_name = rule_row["Rule_Name"]
        policy_name = rule_row["PolicyName"]
        
        # Analyze the rule expression
        rule_analysis = analyze_rule_expression(
            rule_id, 
            rule_expression,
            rule_name=rule_name,
            policy_name=policy_name
        )
        
        # Combine metadata with analysis
        full_rule_json = {
            "rule_metadata": rule_metadata,
            "rule_heuristics": rule_analysis,
            "original_expression": rule_expression
        }
        
        return full_rule_json
    
    except Exception as e:
        print(f"Error generating analysis for rule {rule_row['Rule_Id']}: {e}")
        return {"error": str(e), "rule_id": rule_row["Rule_Id"]}

def save_rule_json(rule_json, rule_id):
    """
    Save rule JSON to file
    
    Args:
        rule_json: The JSON data to save
        rule_id: The ID of the rule
    """
    filename = os.path.join(OUTPUT_DIR, f"rule_{rule_id}_heuristic.json")
    with open(filename, 'w') as f:
        json.dump(rule_json, f, indent=2)
    print(f"Saved rule {rule_id} analysis to {filename}")

def process_rules(num_rules=5, excel_path=None):
    """
    Process rules from the Excel file and generate heuristic analysis
    
    Args:
        num_rules: Number of rules to process (None for all)
        excel_path: Path to the Excel file (defaults to RULES_EXCEL_PATH)
    
    Returns:
        Number of successfully analyzed rules
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
            # Select varied rules based on complexity and policy group
            # Group by policy and take samples from each group
            sample_size = max(1, int(rules_to_process / len(df['PolicyGroup'].unique())))
            samples = []
            
            for policy_group in df['PolicyGroup'].unique():
                policy_df = df[df['PolicyGroup'] == policy_group]
                if len(policy_df) > 0:
                    # Take a sample from each policy group
                    if len(policy_df) <= sample_size:
                        samples.append(policy_df)
                    else:
                        # Sort by expression length to get varied complexity
                        policy_df = policy_df.copy()
                        policy_df['expr_len'] = policy_df['Rule_Expression'].astype(str).apply(len)
                        policy_df = policy_df.sort_values('expr_len')
                        
                        # Get samples from different complexity levels
                        indices = []
                        step = len(policy_df) / sample_size
                        for i in range(sample_size):
                            idx = int(i * step)
                            indices.append(policy_df.iloc[idx].name)
                        
                        samples.append(df.loc[indices])
            
            # Combine samples and limit to requested number
            rules_to_process_df = pd.concat(samples).head(rules_to_process)
        
        success_count = 0
        
        # Process each rule
        for idx, rule in enumerate(rules_to_process_df.iterrows()):
            _, rule_data = rule
            rule_id = rule_data["Rule_Id"]
            print(f"\nProcessing rule {rule_id} ({idx+1}/{rules_to_process}): {rule_data['Rule_Name']}")
            print(f"Expression length: {len(str(rule_data['Rule_Expression']))} characters")
            
            # Generate rule analysis
            start_time = time.time()
            rule_json = generate_rule_heuristic_json(rule_data)
            elapsed_time = time.time() - start_time
            
            # Check if analysis was successful
            if "error" in rule_json:
                print(f"❌ Failed to analyze rule {rule_id}: {rule_json['error']}")
            else:
                print(f"✅ Successfully analyzed rule {rule_id} in {elapsed_time:.2f} seconds")
                success_count += 1
                
                # Save the rule JSON
                save_rule_json(rule_json, rule_id)
        
        # Report success rate
        success_rate = success_count / rules_to_process * 100
        print(f"\nSuccessfully analyzed {success_count}/{rules_to_process} rules ({success_rate:.1f}%)")
        return success_count
        
    except Exception as e:
        print(f"Error processing rules: {e}")
        return 0

def main():
    """
    Main function to run the rule analyzer
    """
    # Process rules to generate heuristic analysis
    process_rules(num_rules=10)
    
    print("\nRule heuristic analysis complete")

if __name__ == "__main__":
    main()