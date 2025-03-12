#!/usr/bin/env python3
"""
Enhanced entity extractor with context-aware extraction.
"""

import os
import json
import base64
import argparse
from openai import OpenAI

def load_context(context_file="compliance_context.json"):
    """Load existing entity context from file if it exists."""
    if os.path.exists(context_file):
        try:
            with open(context_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading entity context: {e}")
    
    return {
        "offensive_content_category": {},  
        "sub_category": {},                
        "guideline": {},                   
        "pending_rules": []                
    }

def get_most_recent_category(context):
    """Get the most recently seen category from context."""
    if not context["offensive_content_category"]:
        return None
    
    primary_category = None
    for category, info in context["offensive_content_category"].items():
        if info.get("is_primary"):
            primary_category = category
            break
    
    return primary_category

def get_recent_subcategories(context, limit=10):
    """Get the most recently seen subcategories from context."""
    if not context["sub_category"]:
        return []
    
    # Sort subcategories by last_seen time
    subcats = [(subcat, info) for subcat, info in context["sub_category"].items()]
    subcats.sort(key=lambda x: x[1].get("last_seen", 0), reverse=True)
    
    # Return the most recent subcategories
    return [subcat for subcat, _ in subcats[:limit]]

def create_context_aware_prompt(system_prompt, user_prompt, context):
    """Create a context-aware prompt by injecting context information."""
    current_category = get_most_recent_category(context)
    recent_subcategories = get_recent_subcategories(context)
    
    # Enhanced system prompt with context
    enhanced_system = system_prompt
    
    # Add context information to user prompt
    context_info = ""
    if current_category:
        context_info += f"Based on previous pages, the current category appears to be: {current_category}\n\n"
    
    if recent_subcategories:
        context_info += "Recent subcategories from previous pages include:\n"
        for subcat in recent_subcategories:
            context_info += f"- {subcat}\n"
        context_info += "\n"
    
    context_info += "If you see content related to these categories or subcategories, include them in your extraction.\n"
    context_info += "When the page doesn't explicitly mention a category, use the current category from context.\n\n"
    
    enhanced_user = context_info + user_prompt
    
    return enhanced_system, enhanced_user

def extract_entities_with_context(api_key, model, system_prompt, user_prompt, context, image_path):
    """Extract entities from an image with context awareness."""
    # Read the image
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Create context-aware prompts
    enhanced_system, enhanced_user = create_context_aware_prompt(system_prompt, user_prompt, context)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Make the API call
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": enhanced_system},
            {"role": "user", "content": [
                {"type": "text", "text": enhanced_user},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
        ],
        max_tokens=2048,
        temperature=0.0,
        response_format={"type": "json_object"},
        timeout=120  # 2 minute timeout
    )
    
    # Parse the response
    result = completion.choices[0].message.content
    
    try:
        extracted_data = json.loads(result)
        return extracted_data
    except json.JSONDecodeError:
        print("Error parsing JSON from API response")
        print(f"Raw response: {result}")
        return {"error": "Failed to parse response"}

def enrich_extraction_with_context(extracted_data, context):
    """Enrich extraction results with context when entities are missing."""
    enriched = extracted_data.copy()
    
    # If no category is found, use the most recent category from context
    if not enriched.get("offensive_content_category"):
        current_category = get_most_recent_category(context)
        if current_category:
            enriched["offensive_content_category"] = current_category
    
    # If no subcategories are found, but there are rules or guidelines,
    # add subcategories from context that might be related
    if (not enriched.get("sub_categories") and 
        (enriched.get("guidelines") or enriched.get("rules"))):
        # Get recent subcategories
        recent_subcats = get_recent_subcategories(context, limit=3)
        if recent_subcats:
            enriched["sub_categories"] = recent_subcats
    
    return enriched

def main():
    parser = argparse.ArgumentParser(description='Extract entities from an image with context awareness')
    parser.add_argument('--image', required=True, help='Path to the image file')
    parser.add_argument('--context-file', default='compliance_context.json', help='Path to the context file')
    parser.add_argument('--api-key', required=True, help='OpenAI API key')
    parser.add_argument('--model', default='gpt-4o', help='OpenAI model to use')
    parser.add_argument('--output', help='Path to save extraction results')
    
    args = parser.parse_args()
    
    # Load context
    context = load_context(args.context_file)
    
    # Load prompts
    with open("entity_system_prompt.txt", "r") as f:
        system_prompt = f.read()
    
    with open("entity_extraction_prompt.txt", "r") as f:
        user_prompt = f.read()
    
    # Extract entities
    extracted_data = extract_entities_with_context(
        args.api_key, args.model, system_prompt, user_prompt, 
        context, args.image
    )
    
    # Enrich with context
    enriched_data = enrich_extraction_with_context(extracted_data, context)
    
    # Print or save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(enriched_data, f, indent=2)
        print(f"Extraction results saved to {args.output}")
    else:
        print(json.dumps(enriched_data, indent=2))

if __name__ == "__main__":
    main()