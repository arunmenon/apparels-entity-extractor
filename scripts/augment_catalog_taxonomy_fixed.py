#!/usr/bin/env python3
"""
Catalog Taxonomy Augmentation Script - Fixed version

This script takes a product taxonomy CSV and augments it with critical attributes
using OpenAI's GPT models. Each product type gets 5-10 essential attributes.
"""

import csv
import json
import os
from typing import List, Dict, Any
import time
import argparse
from openai import OpenAI

# Initialize OpenAI client with API key from environment variable
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

def read_csv_in_batches(file_path: str, batch_size: int = 15) -> List[Dict[str, str]]:
    """Read CSV file in batches, ensuring no duplicate product types"""
    all_products = []
    seen_products = set()
    
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Check if this is a new product type
            product_type = row.get('Product_Type', '')
            if product_type and product_type not in seen_products:
                all_products.append(row)
                seen_products.add(product_type)
    
    # Organize into batches
    batches = []
    for i in range(0, len(all_products), batch_size):
        batch = all_products[i:i+batch_size]
        batches.append(batch)
    
    print(f"Created {len(batches)} batches from {len(all_products)} unique products")
    return batches

def augment_with_attributes(batch: List[Dict[str, str]], model: str = "gpt-4o") -> List[Dict[str, Any]]:
    """Augment products with critical attributes using LLM"""
    
    # Create prompt for the LLM
    prompt = f"""
    For each product type in the following list, identify 5-10 CRITICAL attributes that are absolutely essential 
    for this product type in an e-commerce catalog. Include 2-4 realistic example values for each attribute.
    
    Focus on these attribute types:
    1. PHYSICAL attributes (size, dimensions, weight, color, material)
    2. FUNCTIONAL attributes (features, capabilities, compatibility)
    3. CATEGORICAL attributes (style, type, occasion, certification)
    4. TECHNICAL specifications (power, capacity, performance metrics)
    
    Attribute selection guidelines:
    - Choose attributes that directly impact purchase decisions
    - Select attributes commonly used for filtering/faceting in e-commerce
    - Include attributes needed for inventory/warehouse management
    - Ensure attributes are consistently applicable across similar products
    - Focus on objective rather than subjective attributes
    
    For each product, return a JSON object with these fields:
    - category: The original category
    - product_type_group: The original PTG
    - product_type: The original PT
    - critical_attributes: An array of objects, each with:
      - name: The attribute name (use consistent naming patterns, no abbreviations)
      - type: The type of attribute (PHYSICAL, FUNCTIONAL, CATEGORICAL, TECHNICAL)
      - description: Brief description of why this attribute is critical for this product
      - example_values: Array of 2-4 representative values
      - unit_of_measure: The appropriate unit (if applicable, otherwise null)
      - is_variant_attribute: Boolean indicating if this attribute typically creates product variants
    
    Here's the list of products:
    {json.dumps(batch, indent=2)}
    
    Return ONLY a valid JSON array containing the augmented product information.
    """

    # Call the LLM API
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a product taxonomy expert. You understand product attributes deeply."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    # Extract and parse the response
    try:
        content = response.choices[0].message.content
        # Strip any markdown code block markers
        if "```json" in content:
            content = content.split("```json", 1)[1]
        if "```" in content:
            content = content.split("```", 1)[0]
        # Clean up the content
        content = content.strip()
        
        # Parse the JSON
        augmented_data = json.loads(content)
        return augmented_data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw response: {response.choices[0].message.content}")
        
        # Try to salvage what we can - simplified response
        try:
            # Create a simplified response with just basic product info
            simplified_data = []
            for item in batch:
                simplified_data.append({
                    "category": item.get("Category", ""),
                    "product_type_group": item.get("Product_Type_Group", ""),
                    "product_type": item.get("Product_Type", ""),
                    "critical_attributes": [],
                    "error": "Failed to parse response"
                })
            return simplified_data
        except Exception as inner_e:
            print(f"Failed to create fallback response: {inner_e}")
            return []

def process_file(input_file: str, output_dir: str, batch_size: int = 15, model: str = "gpt-4o", 
               resume_from_batch: int = 0, max_batches: int = None):
    """Process the entire CSV file in batches and save augmented data"""
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Final output file
    output_file = os.path.join(output_dir, "augmented_taxonomy.json")
    
    # Read and organize batches
    batches = read_csv_in_batches(input_file, batch_size)
    
    # How many batches to process
    total_batches = len(batches)
    if max_batches is not None:
        total_batches = min(total_batches, resume_from_batch + max_batches)
    
    print(f"Will process from batch {resume_from_batch+1} to batch {total_batches}")
    
    # Prepare to store all augmented data
    all_augmented_data = []
    
    # Load existing data if available
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                all_augmented_data = json.load(f)
            print(f"Loaded {len(all_augmented_data)} existing products from {output_file}")
        except Exception as e:
            print(f"Error loading existing data: {e}")
    
    # Process new batches
    for i, batch in enumerate(batches[resume_from_batch:total_batches], start=resume_from_batch):
        batch_start_time = time.time()
        batch_output_file = os.path.join(output_dir, f"batch_{i+1}.json")
        
        # Skip if this batch was already processed
        if os.path.exists(batch_output_file) and i >= resume_from_batch:
            print(f"Batch {i+1} already processed, loading from file")
            with open(batch_output_file, 'r', encoding='utf-8') as f:
                try:
                    batch_data = json.load(f)
                    # Check for duplicates before adding
                    existing_pts = {item["product_type"] for item in all_augmented_data}
                    new_items = [item for item in batch_data if item["product_type"] not in existing_pts]
                    all_augmented_data.extend(new_items)
                    print(f"Added {len(new_items)} new items from batch {i+1}")
                    
                    # Skip the API call and continue to next batch
                    continue
                except json.JSONDecodeError:
                    print(f"Error reading batch file {batch_output_file}, will reprocess")
        
        print(f"Processing batch {i+1} of {total_batches}...")
        
        try:
            # Call the API to augment this batch
            augmented_batch = augment_with_attributes(batch, model)
            
            # Save this batch individually (for resume capability)
            with open(batch_output_file, 'w', encoding='utf-8') as f:
                json.dump(augmented_batch, f, indent=2)
            
            # Check for duplicates before adding to the full dataset
            existing_pts = {item["product_type"] for item in all_augmented_data}
            new_items = [item for item in augmented_batch if item["product_type"] not in existing_pts]
            all_augmented_data.extend(new_items)
            
            # Save the complete augmented dataset
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_augmented_data, f, indent=2)
            
            batch_duration = time.time() - batch_start_time
            print(f"Batch {i+1} completed in {batch_duration:.2f} seconds")
            print(f"Total products processed: {len(all_augmented_data)}")
            
            # Calculate and display progress
            progress_pct = ((i + 1) / total_batches) * 100
            remaining_batches = total_batches - (i + 1)
            est_remaining_time = remaining_batches * batch_duration / 60
            print(f"Progress: {progress_pct:.1f}% complete, ~{est_remaining_time:.1f} minutes remaining")
            
        except Exception as e:
            print(f"Error processing batch {i+1}: {e}")
            # Save error log
            error_log = os.path.join(output_dir, f"error_batch_{i+1}.log")
            with open(error_log, 'w', encoding='utf-8') as f:
                f.write(f"Error processing batch {i+1}: {str(e)}\n")
                f.write(f"Batch data: {json.dumps(batch, indent=2)}")
        
        # Avoid rate limiting
        if i < total_batches - 1:
            delay = 3  # Base delay in seconds
            print(f"Waiting {delay} seconds before next batch...")
            time.sleep(delay)
    
    print(f"Processing complete. Results saved to {output_file}")
    print(f"Processed {len(all_augmented_data)} products in total")
    
    # Run duplicate check
    product_types = {}
    for item in all_augmented_data:
        pt = item.get('product_type', '')
        product_types[pt] = product_types.get(pt, 0) + 1
    
    duplicates = {pt: count for pt, count in product_types.items() if count > 1}
    if duplicates:
        print(f"WARNING: Found {len(duplicates)} duplicate product types")
    else:
        print("No duplicates found - data is clean!")
    
    return all_augmented_data

def main():
    parser = argparse.ArgumentParser(description='Augment product taxonomy with critical attributes')
    parser.add_argument('--input', type=str, default='product_taxonomy.csv', help='Input CSV file path')
    parser.add_argument('--output-dir', type=str, default='taxonomy_output', help='Output directory for all files')
    parser.add_argument('--batch-size', type=int, default=15, help='Number of products to process in each batch')
    parser.add_argument('--model', type=str, default='gpt-4o', help='OpenAI model to use')
    parser.add_argument('--resume-from', type=int, default=0, help='Resume processing from this batch number (0-indexed)')
    parser.add_argument('--max-batches', type=int, default=None, help='Maximum number of batches to process')
    parser.add_argument('--test-run', action='store_true', help='Process only first batch for testing')
    
    args = parser.parse_args()
    
    # For test run, process only one batch
    if args.test_run:
        print("Running in TEST MODE - will process only first batch")
        args.max_batches = 1
    
    # Process the file
    process_file(
        args.input, 
        args.output_dir, 
        args.batch_size, 
        args.model, 
        args.resume_from, 
        args.max_batches
    )

if __name__ == "__main__":
    main()