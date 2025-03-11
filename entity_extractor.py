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

# Load the standard prompt from entity_extraction_prompt.txt
with open("entity_extraction_prompt.txt", "r") as prompt_file:
    PROMPT = prompt_file.read()

# Load TOC prompt if it exists, otherwise create default
TOC_PROMPT_FILE = "toc_extraction_prompt.txt"
try:
    with open(TOC_PROMPT_FILE, "r") as toc_file:
        TOC_PROMPT = toc_file.read()
except FileNotFoundError:
    # Default TOC prompt if file doesn't exist
    TOC_PROMPT = """You are a specialized AI assistant for extracting structured data from compliance documents with Table of Contents pages.

TASK:
This page appears to contain a Table of Contents, but may also contain detailed subcategory information. Your job is to:
1. Extract all subcategories listed in the Table of Contents
2. ALSO extract any detailed content about specific subcategories if present (rules, guidelines, etc.)

The document follows a hierarchical structure:
- Offensive_Content_Category (main category like "Firearms & Accessories")
- Sub_Category (specific subcategories like "Ammunition", "Firearm Parts")
- Guidelines (rules and policies related to subcategories)
- Rules (specific prohibition or allowance rules, identified by rule IDs)

DUAL EXTRACTION PROCESS:
- From the TOC section: Extract the main category and ALL listed subcategories
- From any detailed content: Extract subcategory details, guidelines, and rules using the same approach as regular pages

RESPONSE FORMAT:
Provide a Neo4j Cypher query that creates ALL identified entities:
1. The main Offensive_Content_Category node
2. ALL Sub_Category nodes found in both TOC and detailed sections
3. ALL Guidelines and Rules that appear in detailed sections 
4. All appropriate relationships

Example response structure:
```
{
  "cypher_query": "
    MERGE (occ:Offensive_Content_Category {name: 'Main Category Name'})
    
    // Subcategories from TOC
    MERGE (sc1:Sub_Category {name: 'Subcategory 1'})
    MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc1)
    MERGE (sc2:Sub_Category {name: 'Subcategory 2'})
    MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc2)
    
    // If detailed subcategory content exists
    MERGE (g:Guideline {description: 'Detailed guideline for Subcategory 1'})
    MERGE (sc1)-[:HAS_GUIDELINE]->(g)
    
    // Rules if they exist (with both ID-based and descriptive options)
    MERGE (ir:Imperium_Rule {rule_id: '1234', description: 'Specific rule'})
    MERGE (g)-[:PROHIBITS]->(ir)
    
    MERGE (pr:Policy_Rule {description: 'Policy rule without ID'})
    MERGE (g)-[:PROHIBITS]->(pr)
  "
}
```

IMPORTANT NOTES:
1. Process the ENTIRE page - both TOC sections and any detailed content
2. If a subcategory appears in the TOC AND has details elsewhere on the page, create it only ONCE
3. For any subcategory with detailed content, extract guidelines and rules as you would for regular pages
4. Use PROHIBITS/ALLOWS relationship types exactly as shown (not as variables)
5. Always link the entities to maintain proper hierarchy"""
    
    # Write the default prompt to a file for future use
    with open(TOC_PROMPT_FILE, "w") as toc_file:
        toc_file.write(TOC_PROMPT)
    print(f"Created default TOC prompt file: {TOC_PROMPT_FILE}")

# Set your API key and model from the config
API_KEY = os.getenv('OPENAI_API_KEY', '')
MODEL = config['api_model']
GPT4_THREADS = config['gpt4_threads']  # Fetch the GPT-4 thread count
IMAGES_DIR = "output_images"
EXTRACTED_ENTITIES_DIR = "extracted_entities"  # Directory to save JSON files
CONTEXT_FILE = "compliance_context.json"  # File to store the context between pages

# Optional: Get NUM_FILES from environment variable or command-line argument
NUM_FILES = int(os.getenv('NUM_FILES', sys.argv[1]) if len(sys.argv) > 1 else -1)

# Ensure the extracted entities directory exists
os.makedirs(EXTRACTED_ENTITIES_DIR, exist_ok=True)

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds

# Initialize the entity context manager for tracking relationships across pages
context_manager = EntityContextManager(CONTEXT_FILE)


def is_table_of_contents(image_path):
    """Detect if the image is a Table of Contents page or contains TOC sections."""
    try:
        base64_image = encode_image(image_path)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        # Enhanced prompt to detect TOC and hybrid pages
        toc_detection_prompt = """Analyze this document page carefully. We're looking ONLY for pages that have a "Table of Contents" heading followed by bullet points of subcategories.

A true Table of Contents page must contain:
1. A clear "Table of Contents" heading or title
2. Bullet points or a numbered list directly under that heading

Respond with ONE of these exact options:
- "FULL_TOC" if it's primarily a Table of Contents page
- "HYBRID" if it contains both TOC elements and detailed category content
- "REGULAR" if it's a regular content page with no TOC elements"""

        # Payload for TOC detection
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": toc_detection_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 50,
            "temperature": 0
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if "choices" in result and result['choices']:
            content = result["choices"][0]["message"]["content"].strip().upper()
            print(f"Page type detection for {image_path}: {content}")
            
            # Both FULL_TOC and HYBRID should use the TOC prompt
            if "FULL_TOC" in content or "HYBRID" in content:
                return True
                
            # Better debug logging
            if "HYBRID" in content:
                print(f"Detected hybrid TOC/content page for {image_path}")
            elif "FULL_TOC" in content:
                print(f"Detected full TOC page for {image_path}")
            else:
                print(f"Detected regular content page for {image_path}")
                
        return False
    
    except Exception as e:
        print(f"Error detecting page type in {image_path}: {str(e)}")
        if hasattr(e, 'response') and e.response:
            try:
                error_detail = e.response.json()
                print(f"API error details: {error_detail}")
            except:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
        return False

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

            # Print model being used for debugging
            print(f"Using model: {MODEL}")
            
            # Check if this is a TOC page and use appropriate prompt
            is_toc = is_table_of_contents(image_path)
            
            # Select the prompt based on page type
            current_prompt = TOC_PROMPT if is_toc else PROMPT
            
            if is_toc:
                print(f"Using TOC prompt for {image_path}")
            
            # Updated payload structure compatible with both gpt-4o and vision models
            payload = {
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": current_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
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
                error_message = f"API returned an error: {response.status_code} for image {image_path}"
                try:
                    error_details = response.json()
                    error_message += f" - Details: {error_details}"
                except:
                    pass
                print(error_message)
                return None

            result = response.json()

            if 'choices' in result and result['choices']:
                structured_response = result['choices'][0]['message']['content'].strip()

                # Debugging: Log the raw response before any processing
                print(f"Raw structured response: {structured_response}")

                # Remove backticks and any language label
                if structured_response.startswith("```"):
                    # Extract content between triple backticks
                    start_idx = structured_response.find("\n", structured_response.find("```"))
                    if start_idx != -1:
                        end_idx = structured_response.rfind("```")
                        if end_idx != -1:
                            structured_response = structured_response[start_idx:end_idx].strip()
                        else:
                            structured_response = structured_response[start_idx:].strip()
                    else:
                        structured_response = structured_response.replace("```", "").strip()
                
                # Handle cypher format specifically
                if structured_response.startswith("cypher"):
                    structured_response = structured_response[6:].strip()
                
                # Preserve newlines for readability in Cypher queries
                cypher_query = None
                if '"cypher_query":' in structured_response:
                    # Extract just the cypher query to preserve its formatting
                    start_idx = structured_response.find('"cypher_query":')
                    if start_idx != -1:
                        query_start = structured_response.find('"', start_idx + 15)
                        if query_start != -1:
                            query_end = structured_response.rfind('"')
                            if query_end > query_start:
                                cypher_query = structured_response[query_start+1:query_end]
                
                # Special handling for JSON with control characters
                try:
                    # Try direct JSON parsing first (handles most well-formed JSON responses)
                    json_obj = json.loads(structured_response)
                    # If successful, convert back to string with proper formatting
                    structured_response = json.dumps(json_obj)
                    return structured_response
                except json.JSONDecodeError:
                    # If direct parsing fails, try more aggressive cleaning
                    pass
                
                # Extract just the cypher query from code block and create a clean JSON
                if "cypher_query" in structured_response:
                    try:
                        # For JSON code block format
                        start_idx = structured_response.find("cypher_query")
                        if start_idx != -1:
                            # Find the start of the query value
                            quote_idx = structured_response.find('"', start_idx + 13)
                            if quote_idx != -1:
                                # Find the next quote that's followed by a closing brace or comma
                                end_idx = 0
                                for i in range(quote_idx + 1, len(structured_response)):
                                    if structured_response[i] == '"' and i+1 < len(structured_response):
                                        if structured_response[i+1] in [',', '}']:
                                            end_idx = i
                                            break
                                
                                if end_idx > 0:
                                    # Extract the raw cypher query
                                    cypher_query = structured_response[quote_idx+1:end_idx]
                                    # Create a clean JSON with just this query
                                    clean_json = f'{{"cypher_query": "{cypher_query.replace("\n", "\\n").replace("\"", "\\\"")}"}}'
                                    try:
                                        # Validate it's proper JSON
                                        json.loads(clean_json)
                                        return clean_json
                                    except:
                                        pass
                    except Exception as e:
                        print(f"Error extracting cypher query: {e}")
                
                # Remove all control characters except spaces
                import re
                structured_response = re.sub(r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', structured_response)
                
                # Replace newlines with spaces except in the cypher query
                if not cypher_query:
                    structured_response = structured_response.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                
                # Ensure valid JSON structure, add braces if necessary
                if not structured_response.startswith('{') and not structured_response.endswith('}'):
                    structured_response = '{' + structured_response + '}'
                
                # Put back the formatted cypher query if we extracted it
                if cypher_query:
                    try:
                        # Find cypher_query field
                        if '"cypher_query":' in structured_response:
                            # Create a clean JSON with just the cypher query
                            clean_json = f'{{"cypher_query": "{cypher_query}"}}'
                            return clean_json
                    except Exception as e:
                        print(f"Error reconstructing JSON with cypher query: {e}")
                
                # Final attempt to clean and validate
                try:
                    # Validate JSON structure
                    json_obj = json.loads(structured_response)
                    # If successful, convert back to string with proper formatting
                    return json.dumps(json_obj)
                except json.JSONDecodeError as e:
                    print(f"Warning: JSON cleaning failed, returning raw string. Error: {e}")
                    # Return the cleaned but possibly invalid JSON
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
