#!/usr/bin/env python3
"""
Test script using new screenshot for more accurate extraction
"""

import os
import time
import json
import base64
import logging
import argparse
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def encode_image(image_path):
    """Encodes an image as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def main():
    """Run extraction test with new image."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test TOC extraction with a specific image")
    parser.add_argument("--image", "-i", 
                        help="Path to the image file (default: output_images/page_1.png)",
                        default="output_images/page_1.png")
    parser.add_argument("--max-tokens", "-t", type=int, default=2048,
                        help="Maximum tokens for completion (default: 2048)")
    args = parser.parse_args()
    
    # Set up variables
    img_path = args.image
    max_tokens = args.max_tokens
    
    logger = logging.getLogger("test_extraction")
    start_time = time.time()
    
    print("\n=== IMAGE EXTRACTION TEST ===")
    
    # Check if the image exists
    if not os.path.exists(img_path):
        print(f"Error: Image not found at {img_path}")
        return 1
    
    print(f"Loading image: {img_path}...")
    base64_img = encode_image(img_path)
    
    # Load prompts
    print("Loading prompts...")
    with open("toc_system_prompt.txt", "r") as f:
        system_prompt = f.read()
    with open("toc_extraction_prompt.txt", "r") as f:
        user_prompt = f.read()
    
    # Setup API client
    api_key = os.getenv('OPENAI_API_KEY', '')
    client = OpenAI(api_key=api_key)
    
    # Make the call
    print(f"\nSending API request at {time.strftime('%H:%M:%S')}...")
    api_start = time.time()
    
    model = "gpt-4o"
    temperature = 0.0
    
    print(f"Parameters: model={model}, max_tokens={max_tokens}, temperature={temperature}")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                ]}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        
        api_duration = time.time() - api_start
        print(f"API call completed in {api_duration:.2f} seconds")
        print(f"Tokens used: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        # Parse the response
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # Generate output filename based on input image
        base_name = os.path.basename(img_path).split('.')[0]
        output_file = f"{base_name}_test_output.json"
        
        # Save the raw response
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        
        # Extract subcategories
        subcategories = result.get("sub_categories", [])
        print(f"\nExtracted {len(subcategories)} subcategories")
        
        # Load ground truth for comparison
        with open("ground_truth_subcategories.json", "r") as f:
            ground_truth_data = json.load(f)
            ground_truth = ground_truth_data.get("subcategories", [])
        
        # Calculate accuracy metrics
        extracted = set(subcategories)
        truth = set(ground_truth)
        
        # Find matching and incorrect items
        matching = extracted.intersection(truth)
        missing = truth - extracted
        hallucinated = extracted - truth
        
        # Calculate precision, recall, and F1
        correct = len(matching)
        precision = correct / len(extracted) if extracted else 0
        recall = correct / len(truth) if truth else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Print results
        print("\n=== VALIDATION RESULTS ===")
        print(f"Ground truth items: {len(truth)}")
        print(f"Extracted items: {len(extracted)}")
        print(f"Correctly extracted: {correct}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall: {recall:.4f}")
        print(f"F1 Score: {f1:.4f}")
        
        if matching:
            print(f"\nCorrectly extracted items ({len(matching)}):")
            for item in sorted(matching)[:5]:  # Show first 5
                print(f"  ✓ {item}")
            if len(matching) > 5:
                print(f"  ... and {len(matching) - 5} more")
        
        if missing:
            print(f"\nMissing items ({len(missing)}):")
            for item in sorted(missing)[:10]:  # Show first 10
                print(f"  - {item}")
            if len(missing) > 10:
                print(f"  ... and {len(missing) - 10} more")
        
        if hallucinated:
            print(f"\nIncorrect items ({len(hallucinated)}):")
            for item in sorted(hallucinated)[:10]:  # Show first 10
                print(f"  + {item}")
            if len(hallucinated) > 10:
                print(f"  ... and {len(hallucinated) - 10} more")
        
        print(f"\nFull results saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    
    total_duration = time.time() - start_time
    print(f"\nTotal test execution time: {total_duration:.2f} seconds")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())