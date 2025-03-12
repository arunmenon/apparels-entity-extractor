import os
import requests
import json
import time
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import encode_image
from entity_context_manager import EntityContextManager

# Global regex patterns for extraction
CATEGORY_PATTERN = re.compile(r'MERGE\s+\((?:occ|c):Offensive_Content_Category\s+\{name:\s*\'([^\']+)\'\}\)')
SUBCATEGORY_PATTERN = re.compile(r'MERGE\s+\((?:sc\d+|s\d+):Sub_Category\s+\{name:\s*\'([^\']+)\'\}\)')
CYPHER_QUERY_PATTERN = re.compile(r'"cypher_query"\s*:\s*"(.*?)(?:"\s*}|$)', re.DOTALL)

# Load the configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Load the prompts for system and user messages
with open("entity_extraction_prompt.txt", "r") as prompt_file:
    USER_PROMPT = prompt_file.read()

with open("entity_system_prompt.txt", "r") as system_prompt_file:
    SYSTEM_PROMPT = system_prompt_file.read()

# Load TOC prompts
TOC_USER_PROMPT_FILE = "toc_extraction_prompt.txt"
TOC_SYSTEM_PROMPT_FILE = "toc_system_prompt.txt"

try:
    with open(TOC_USER_PROMPT_FILE, "r") as toc_file:
        TOC_USER_PROMPT = toc_file.read()
except FileNotFoundError:
    # Create a default if missing
    TOC_USER_PROMPT = "Extract all subcategories from the Table of Contents section. Return ONLY a valid JSON object with a single \"cypher_query\" field."
    with open(TOC_USER_PROMPT_FILE, "w") as toc_file:
        toc_file.write(TOC_USER_PROMPT)
    print(f"Created default TOC user prompt file: {TOC_USER_PROMPT_FILE}")

try:
    with open(TOC_SYSTEM_PROMPT_FILE, "r") as toc_system_file:
        TOC_SYSTEM_PROMPT = toc_system_file.read()
except FileNotFoundError:
    # Create a default if missing
    TOC_SYSTEM_PROMPT = """You are a specialized AI assistant for extracting subcategories from Table of Contents pages in compliance documents.

For Table of Contents pages:
1. Identify the main Offensive_Content_Category
2. Extract EVERY bullet point under the TOC heading as a complete Sub_Category
3. Keep the EXACT text of each bullet point without modifications
4. Never repeat subcategories - each should appear EXACTLY ONCE
5. Include ALL subcategories from the TOC (do not stop at a specific number)

MOST IMPORTANT: Return ONLY a JSON object containing a "cypher_query" field with the Neo4j query.
DO NOT repeat any instructions in your response."""
    
    with open(TOC_SYSTEM_PROMPT_FILE, "w") as toc_system_file:
        toc_system_file.write(TOC_SYSTEM_PROMPT)
    print(f"Created default TOC system prompt file: {TOC_SYSTEM_PROMPT_FILE}")

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
        toc_detection_prompt = """You are a document classifier that identifies Table of Contents pages. A true Table of Contents page must contain a clear "Table of Contents" heading or title followed by bulleted or numbered lists of subcategories."""

        # Standard payload for TOC detection
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": toc_detection_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Is this a Table of Contents page? Only classify as TOC if there's an explicit 'Table of Contents' heading with visible bullet points. Respond with ONLY ONE of these exact options:\n- \"FULL_TOC\" if it's primarily a Table of Contents page\n- \"HYBRID\" if it contains both TOC elements and detailed category content\n- \"REGULAR\" if it's a regular content page with no TOC elements"},
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
            
            # Better debug logging and return values
            if "HYBRID" in content:
                print(f"Detected hybrid TOC/content page for {image_path}")
                return True
            elif "FULL_TOC" in content:
                print(f"Detected full TOC page for {image_path}")
                return True
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

def extract_subcategories_from_text(text):
    """Extract subcategories from text using various regex patterns"""
    subcats = []
    
    # Try a series of patterns, from specific to general
    patterns = [
        r"MERGE \(sc\d+:Sub_Category \{name: '([^']+)'\}\)",  # Standard pattern
        r"MERGE \(s\d+:Sub_Category \{name: '([^']+)'\}\)",   # Alternative naming
        r"Sub_Category\s*\{name:\s*'([^']+)'\}",              # More flexible
        r"{name:\s*'([^']+)'}"                                # Most general
    ]
    
    # Try each pattern
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                if match and match not in subcats:
                    subcats.append(match)
    
    # If we found subcategories, return them
    if subcats:
        return subcats
    
    # Last resort: Look for anything in quotes that might be a subcategory
    potential_subcats = re.findall(r"'([^']+)'", text)
    return [s for s in potential_subcats if len(s) > 3 and s not in subcats]  # Filter out short strings

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
            
            # Select the appropriate system and user prompts based on page type
            system_prompt = TOC_SYSTEM_PROMPT if is_toc else SYSTEM_PROMPT
            user_prompt = TOC_USER_PROMPT if is_toc else USER_PROMPT
            
            if is_toc:
                print(f"Using TOC prompts for {image_path}")
            
            # Updated payload structure with separate system and user messages
            # Use a lower token limit for TOC extraction to avoid excessive responses
            max_tokens = 1024 if is_toc else 3072
            
            # Standard payload for GPT-4 models
            payload = {
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens,
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

                # Debugging: Log the raw response
                print(f"Raw structured response: {structured_response[:2000]}...")
                
                # Direct fix for TOC extraction - extract subcategories from raw output
                if is_toc and "Sub_Category" in structured_response:
                    subcats = extract_subcategories_from_text(structured_response)
                    if subcats:
                        # Extract category if possible
                        category_match = CATEGORY_PATTERN.search(structured_response)
                        category_name = category_match.group(1) if category_match else "Firearms & Accessories"
                        
                        print(f"TOC Direct extraction: Found {len(subcats)} subcategories")
                        
                        # Build a clean Cypher query
                        cypher_query = f"MERGE (occ:Offensive_Content_Category {{name: '{category_name}'}}) "
                        
                        for i, subcat in enumerate(subcats[:40], 1):  # Limit to 40 subcats max
                            cypher_query += f"MERGE (sc{i}:Sub_Category {{name: '{subcat}'}}) "
                            cypher_query += f"MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc{i}) "
                        
                        # Return this as a properly formatted JSON
                        return json.dumps({"cypher_query": cypher_query})
                
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
                
                # Check for safety filter responses
                if "I'm sorry, I can't assist with that" in structured_response or "I apologize, but I cannot" in structured_response:
                    print(f"Detected safety filter response. Creating minimal JSON with empty query.")
                    return json.dumps({"cypher_query": ""})
                
                # Special handling for responses containing subcategories (regardless of JSON validity)
                if "Sub_Category" in structured_response:
                    try:
                        # Try to extract subcategories directly from the response
                        subcats = extract_subcategories_from_text(structured_response)
                        
                        if subcats:
                            # Look for category name
                            category_match = CATEGORY_PATTERN.search(structured_response)
                            category_name = category_match.group(1) if category_match else "Firearms & Accessories"
                            
                            # Build a clean, minimal Cypher query
                            cypher_query = f"MERGE (occ:Offensive_Content_Category {{name: '{category_name}'}}) "
                            
                            for i, subcat in enumerate(subcats[:40], 1):  # Limit to 40 subcats max
                                cypher_query += f"MERGE (sc{i}:Sub_Category {{name: '{subcat}'}}) "
                                cypher_query += f"MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc{i}) "
                            
                            # Return as proper JSON
                            print(f"Fixed TOC JSON with {len(subcats)} subcategories")
                            return json.dumps({"cypher_query": cypher_query})
                    except Exception as e:
                        print(f"Error fixing TOC JSON: {str(e)}")
                        # Fallback - create minimal JSON
                        return json.dumps({"cypher_query": "MERGE (occ:Offensive_Content_Category {name: 'Firearms & Accessories'})"})
                
                # Special handling for JSON with backticks
                if "```json" in structured_response and "cypher_query" in structured_response:
                    try:
                        # Extract JSON content from code block
                        json_block_start = structured_response.find('```json')
                        json_block_end = structured_response.find('```', json_block_start + 7)
                        
                        if json_block_start != -1 and json_block_end != -1:
                            # Extract the content between the markers and trim whitespace
                            json_content = structured_response[json_block_start + 7:json_block_end].strip()
                            
                            # Try to parse and validate
                            try:
                                json_obj = json.loads(json_content)
                                return json.dumps(json_obj)
                            except:
                                # Just return the extracted content
                                return json_content
                    except Exception as e:
                        print(f"Error extracting JSON from code block: {e}")
                
                # Special handling for JSON with control characters
                try:
                    # Try direct JSON parsing first (handles most well-formed JSON responses)
                    json_obj = json.loads(structured_response)
                    # If successful, convert back to string with proper formatting
                    structured_response = json.dumps(json_obj)
                    return structured_response
                except json.JSONDecodeError as json_err:
                    # If the response is TOC extraction, we have special handling for that
                    if "```cypher" in structured_response or ('"cypher_query"' in structured_response and 'Sub_Category' in structured_response):
                        # Try to extract TOC information directly from the raw response
                        # This is handled by the special case in the first page extraction code
                        pass
                        
                    # Print detailed error for debugging
                    print(f"JSON parse error details: {json_err}")
                    print(f"Error position: {json_err.pos}")
                    if json_err.pos is not None and json_err.pos < len(structured_response):
                        error_context = structured_response[max(0, json_err.pos - 10):min(len(structured_response), json_err.pos + 10)]
                        error_char = repr(structured_response[json_err.pos]) if json_err.pos < len(structured_response) else "N/A"
                        print(f"Error context: ...{error_context}...")
                        print(f"Character at error position: {error_char}")
                        
                        # Handle the specific error we're seeing
                        if "Invalid control character" in str(json_err) and json_err.pos < len(structured_response):
                            # Try explicit string cleaning
                            # First, try to fix the specific problem (newline after opening quote)
                            if '"cypher_query": "' in structured_response:
                                print("Fixing newline after opening quote...")
                                # Replace the newline after the opening quote with an empty string
                                fixed_response = structured_response.replace('"cypher_query": "\n', '"cypher_query": "')
                                try:
                                    json_obj = json.loads(fixed_response)
                                    return json.dumps(json_obj)
                                except:
                                    # If that didn't work, try a more aggressive replacement
                                    fixed_response = structured_response.replace('\n', ' ').replace('\r', ' ')
                                    # Clean up double spaces
                                    while '  ' in fixed_response:
                                        fixed_response = fixed_response.replace('  ', ' ')
                                    structured_response = fixed_response
                                    try:
                                        json_obj = json.loads(structured_response)
                                        return json.dumps(json_obj)
                                    except:
                                        pass
                    
                    # If direct parsing fails, try more aggressive cleaning
                    pass
                
                # Extract just the cypher query from code block and create a clean JSON
                if "cypher_query" in structured_response:
                    try:
                        # Handle the specific format we're seeing in errors: ```json\n{ "cypher_query": "\n...
                        if '```json' in structured_response and 'cypher_query' in structured_response:
                            print("Using pattern matching fallback for JSON code block...")
                            # Extract the raw content from the code block
                            try:
                                # First, find the JSON content between ```json and ```
                                json_block_start = structured_response.find('```json')
                                json_block_end = structured_response.find('```', json_block_start + 7)
                                if json_block_start != -1 and json_block_end != -1:
                                    # Extract the content between the markers and trim whitespace
                                    json_content = structured_response[json_block_start + 7:json_block_end].strip()
                                    
                                    # Extract the Cypher query if possible
                                    if '"cypher_query"' in json_content:
                                        # Simplest approach: use regex to extract the content between quotes
                                        import re
                                        query_match = re.search(r'"cypher_query":\s*"(.*?)"(?=\s*}[\s\n]*$)', json_content, re.DOTALL)
                                        if query_match:
                                            query_text = query_match.group(1)
                                            # Properly escape the query text
                                            query_text = query_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
                                            # Create a fresh, clean JSON object
                                            clean_json = f'{{"cypher_query": "{query_text}"}}'
                                            try:
                                                json.loads(clean_json)  # Validate it's proper JSON
                                                return clean_json
                                            except json.JSONDecodeError as je:
                                                print(f"Warning: Clean JSON still invalid: {je}")
                                    
                                    # Second approach: try to remove just the newlines and control characters
                                    # Keep the structure but convert newlines and control chars
                                    clean_content = re.sub(r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', json_content)
                                    clean_content = re.sub(r'\n\s*', ' ', clean_content)
                                    try:
                                        json_obj = json.loads(clean_content)
                                        return json.dumps(json_obj)
                                    except json.JSONDecodeError:
                                        pass
                            except Exception as e:
                                print(f"Error in JSON extraction: {e}")
                        
                        # For other formats, use the original approach
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
                    # Final fallback for responses with cypher_query
                    if "cypher_query" in structured_response and not structured_response.strip().startswith("{"):
                        # If we reach here, we have a non-JSON response with a cypher_query
                        # Extract anything that looks like a valid Cypher query pattern
                        import re
                        # Look for a pattern like: MERGE (occ:Offensive_Content_Category {name: 'something'})
                        pattern = r'MERGE\s*\(\w+:[\w_]+\s*\{[^}]+\}\)'
                        matches = re.findall(pattern, structured_response)
                        if matches:
                            # We found some valid Cypher MERGE statements, let's construct a minimal JSON
                            query_content = " ".join(matches)
                            minimal_json = f'{{"cypher_query": "{query_content}"}}'
                            return minimal_json
                    
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
                try:
                    # First, try to extract the primary category directly from the raw response
                    img_name = os.path.splitext(os.path.basename(first_image))[0]
                    page_num = int(img_name.split("_")[-1]) if "_" in img_name else 0
                    
                    # Look for the main category first using regex
                    category_match = CATEGORY_PATTERN.search(first_response)
                    if category_match:
                        primary_category = category_match.group(1)
                        print(f"Found primary category in first page: '{primary_category}'")
                    else:
                        primary_category = "Firearms & Accessories"  # Default value
                        print(f"Using default primary category: '{primary_category}'")
                    
                    # Extract subcategories directly from the raw response using our helper function
                    unique_subcats = extract_subcategories_from_text(first_response)
                    
                    # Anti-hallucination measure: If we get too many subcategories, it's likely hallucination
                    # Limit to a reasonable number (TOC pages typically have 20-50 items)
                    if len(unique_subcats) > 50:
                        print(f"Warning: Found {len(unique_subcats)} subcategories, which is suspiciously high. Limiting to first 50.")
                        unique_subcats = unique_subcats[:50]
                    
                    print(f"Found {len(unique_subcats)} unique subcategories for TOC")
                    
                    # Create a simplified Cypher query with just the main category and subcategories
                    cypher_query = f"MERGE (occ:Offensive_Content_Category {{name: '{primary_category}'}}) "
                    
                    for i, subcat in enumerate(unique_subcats, 1):
                        cypher_query += f"MERGE (sc{i}:Sub_Category {{name: '{subcat}'}}) "
                        cypher_query += f"MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc{i}) "
                    
                    # Create and save a minimal JSON
                    minimal_json = {"cypher_query": cypher_query}
                    
                    # Process with context manager to establish primary category
                    enriched_response = context_manager.process_page_extraction(page_num, minimal_json)
                    
                    # Save the first page response
                    output_file = os.path.join(EXTRACTED_ENTITIES_DIR, f"extracted_{img_name}.json")
                    with open(output_file, "w") as f:
                        json.dump(enriched_response, f, indent=4)
                    
                    print(f"Processed and saved first page with manually built TOC extract.")
                except Exception as e:
                    print(f"Error processing first page: {e}")
                    # Fallback to a very simple primary category only
                    if primary_category:
                        # Create the simplest possible extract with just the main category
                        minimal_json = {"cypher_query": f"MERGE (occ:Offensive_Content_Category {{name: '{primary_category}'}})"} 
                        try:
                            # Save this minimal version
                            img_name = os.path.splitext(os.path.basename(first_image))[0]
                            output_file = os.path.join(EXTRACTED_ENTITIES_DIR, f"extracted_{img_name}.json")
                            with open(output_file, "w") as f:
                                json.dump(minimal_json, f, indent=4)
                            print(f"Saved simplified primary category for first page.")
                        except Exception as inner_e:
                            print(f"Failed to save primary category: {inner_e}")
                
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
