import os
import requests
import json
import time
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import encode_image
from entity_context_manager import EntityContextManager

# Load the configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Load the prompt from entity_extraction_prompt.txt
with open("entity_extraction_prompt.txt", "r") as prompt_file:
    PROMPT = prompt_file.read()

# Set your API key and model from the config
API_KEY = os.getenv('OPENAI_API_KEY', 'your_openai_api_key')
MODEL = config['api_model']
GPT4_THREADS = config['gpt4_threads']  # Fetch the GPT-4 thread count
IMAGES_DIR = "output_images"
EXTRACTED_ENTITIES_DIR = "extracted_entities_improved"  # Directory to save JSON files
CONTEXT_FILE = "compliance_context_improved.json"  # File to store the context between pages

# Optional: Get NUM_FILES from environment variable or command-line argument
NUM_FILES = int(os.getenv('NUM_FILES', sys.argv[1]) if len(sys.argv) > 1 else -1)

# Ensure the extracted entities directory exists
os.makedirs(EXTRACTED_ENTITIES_DIR, exist_ok=True)

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds

# Initialize the entity context manager for tracking relationships across pages
context_manager = EntityContextManager(CONTEXT_FILE)


def gpt4_vision_compliance_extraction(image_path):
    """Send an image to GPT-4 Vision model for compliance entity extraction with retry and backoff logic."""
    retries = 0
    backoff = INITIAL_BACKOFF

    while retries < MAX_RETRIES:
        try:
            base64_image = encode_image(image_path)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            }

            payload = {
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 3072,  # Increased token limit for complex compliance rules
                "temperature": 0
            }

            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

            # Check for 429 (Too Many Requests) and retry with backoff
            if response.status_code == 429:
                print(f"Rate limit reached for image {image_path}. Retrying in {backoff} seconds...")
                time.sleep(backoff)  # Backoff before retrying
                retries += 1
                backoff *= 2  # Exponential backoff
                continue  # Retry the request

            # If other error status codes
            if response.status_code != 200:
                print(f"API returned an error: {response.status_code} for image {image_path}")
                return None

            result = response.json()

            if 'choices' in result and result['choices']:
                structured_response = result['choices'][0]['message']['content'].strip()

                # Debugging: Log the raw response before any processing
                print(f"Raw structured response: {structured_response}")

                # Remove backticks and the "json" label if they are present
                if structured_response.startswith("```json"):
                    structured_response = structured_response.strip("```json").strip("```").strip()
                
                # Replace control characters that can cause JSON parsing errors
                structured_response = structured_response.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                
                # Ensure valid JSON structure, add braces if necessary
                if not structured_response.startswith('{') and not structured_response.endswith('}'):
                    structured_response = '{' + structured_response + '}'

                return structured_response
            else:
                print(f"No valid response for {image_path}")
                return None

        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            return None

    print(f"Max retries reached for image {image_path}. Skipping.")
    return None

def process_compliance_images_with_gpt4():
    """Send all compliance document images in the directory to GPT-4 for entity extraction using multithreading."""
    # Get a sorted list of images to ensure we process them in order by page number
    # Only include files that start with "page_" to avoid processing other images
    images = [os.path.join(IMAGES_DIR, img) for img in os.listdir(IMAGES_DIR) 
              if img.endswith(".png") and img.startswith("page_")]
    
    # Extract page number and sort by it
    def get_page_num(path):
        try:
            filename = os.path.basename(path)
            return int(filename.replace("page_", "").replace(".png", ""))
        except ValueError:
            return 0
    
    # Sort by page number
    images.sort(key=get_page_num)

    # If NUM_FILES is passed, limit the number of files to process
    if NUM_FILES > 0:
        images = images[:NUM_FILES]
    
    total_images = len(images)
    if total_images == 0:
        print("No images found to process.")
        return
    
    processed_images = 0
    primary_category = None
    
    print(f"Starting to process {total_images} pages...")
    
    # Step 1: Process the first page serially to establish the primary category
    if total_images > 0:
        print("Processing first page serially to establish primary category...")
        first_image = images[0]
        first_response = gpt4_vision_compliance_extraction(first_image)
        processed_images += 1
        
        if first_response:
            try:
                # Process the first page response to establish the primary category
                json_response = json.loads(first_response)
                
                # Extract page number from filename
                img_name = os.path.splitext(os.path.basename(first_image))[0]
                page_num = int(img_name.split("_")[-1]) if "_" in img_name else 0
                
                # Process with context manager to establish primary category
                enriched_response = context_manager.process_page_extraction(page_num, json_response)
                
                # Get the category from the first page's cypher query
                if 'cypher_query' in enriched_response:
                    cypher_query = enriched_response['cypher_query']
                    category_pattern = r"MERGE \(occ:Offensive_Content_Category \{name: '([^']+)'\}\)"
                    category_matches = re.findall(category_pattern, cypher_query)
                    if category_matches:
                        primary_category = category_matches[0]
                        print(f"Found primary category in first page: '{primary_category}'")
                
                # Save the first page response
                output_file = os.path.join(EXTRACTED_ENTITIES_DIR, f"extracted_{img_name}.json")
                with open(output_file, "w") as f:
                    json.dump(enriched_response, f, indent=4)
                
                print(f"Processed and saved first page.")
                print(f"Progress: 1/{total_images} pages processed ({(1/total_images)*100:.1f}%)")
            except Exception as e:
                print(f"Error processing first page: {e}")
    
    # Step 2: If no category found in first page response, try context manager
    if not primary_category:
        for cat, info in context_manager.entity_context['offensive_content_category'].items():
            if info.get('is_primary'):
                primary_category = cat
                break
    
    # Step 3: If still no primary category, default to something generic
    if not primary_category:
        primary_category = "Root Category"  # Generic default, will be replaced by the first actual category
        print(f"No primary category found. Using default: '{primary_category}'")
    else:
        print(f"Using primary category: '{primary_category}'")
    
    # Step 4: Process the remaining pages in parallel
    remaining_images = images[1:] if total_images > 1 else []
    
    if remaining_images:
        print(f"Processing remaining {len(remaining_images)} pages in parallel...")
        
        with ThreadPoolExecutor(max_workers=GPT4_THREADS) as executor:
            futures = {executor.submit(gpt4_vision_compliance_extraction, img_path): img_path 
                       for img_path in remaining_images}
            
            for future in as_completed(futures):
                image_path = futures[future]
                
                try:
                    # Get the response from GPT-4
                    response = future.result()
                    processed_images += 1
                    
                    # Print progress
                    print(f"Progress: {processed_images}/{total_images} pages processed ({(processed_images/total_images)*100:.1f}%)")
                    
                    # Skip if no response
                    if not response:
                        continue
                    
                    # Process valid JSON
                    try:
                        # Parse the JSON
                        json_response = json.loads(response)
                        
                        # Extract page number from filename
                        img_name = os.path.splitext(os.path.basename(image_path))[0]
                        page_num = int(img_name.split("_")[-1]) if "_" in img_name else 0
                        
                        # Process with context manager
                        enriched_response = context_manager.process_page_extraction(page_num, json_response)
                        
                        # Normalize the category to the primary category
                        if 'cypher_query' in enriched_response:
                            cypher_query = enriched_response['cypher_query']
                            
                            # Replace all category references with the primary category
                            category_pattern = r"MERGE \(occ:Offensive_Content_Category \{name: '[^']+'\}\)"
                            normalized_query = re.sub(
                                category_pattern,
                                f"MERGE (occ:Offensive_Content_Category {{name: '{primary_category}'}})",
                                cypher_query
                            )
                            
                            # Update if changed
                            if normalized_query != cypher_query:
                                enriched_response['cypher_query'] = normalized_query
                                print(f"Normalized Cypher query for page {page_num} to use primary category '{primary_category}'")
                        
                        # Save the result
                        output_file = os.path.join(EXTRACTED_ENTITIES_DIR, f"extracted_{img_name}.json")
                        with open(output_file, "w") as f:
                            json.dump(enriched_response, f, indent=4)
                        
                        print(f"Saved entities from page {page_num} to {output_file}")
                    
                    except json.JSONDecodeError as e:
                        print(f"Error: Invalid JSON for image {image_path}. Error: {e}. Skipping this image.")
                
                except Exception as e:
                    print(f"Error processing result for image {image_path}: {e}")
    
    # Step 5: After processing all pages, clean up and generate any remaining relationships
    context_manager.generate_cypher_for_orphaned_rules()

if __name__ == "__main__":
    print("Starting GPT-4 Vision compliance extraction with context tracking...")
    process_compliance_images_with_gpt4()
    print("GPT-4 Vision compliance extraction complete with context tracking.")
