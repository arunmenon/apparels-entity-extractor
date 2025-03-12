#!/usr/bin/env python3
"""
Minimal test script to diagnose TOC extraction performance issues.
Bypasses all the complex logic and focuses just on the API call.
"""

import os
import time
import json
import base64
from openai import OpenAI

def encode_image(image_path):
    """Encodes an image as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def main():
    """Run a minimal extraction test."""
    print("\n=== MINIMAL EXTRACTION TEST ===")
    start_time = time.time()
    
    # Load image
    print("Loading image...")
    img_path = "output_images/page_1.png"
    base64_img = encode_image(img_path)
    
    # Load prompt
    print("Loading prompt...")
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
    
    # First test with minimal tokens
    model = "gpt-4o"
    max_tokens = 1024
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
        
        # Get response content and truncate for display
        content = response.choices[0].message.content
        preview = content[:200] + "..." if len(content) > 200 else content
        print(f"\nResponse preview:\n{preview}")
        
        # Save full response
        with open("minimal_test_output.json", "w") as f:
            f.write(content)
            
        print(f"\nFull response saved to minimal_test_output.json")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    
    total_duration = time.time() - start_time
    print(f"\nTotal test execution time: {total_duration:.2f} seconds")

if __name__ == "__main__":
    main()