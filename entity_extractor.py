import os
import requests
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import encode_image

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
EXTRACTED_ENTITIES_DIR = "extracted_entities"  # Directory to save JSON files

# Optional: Get NUM_FILES from environment variable or command-line argument
NUM_FILES = int(os.getenv('NUM_FILES', sys.argv[1]) if len(sys.argv) > 1 else -1)

# Ensure the extracted entities directory exists
os.makedirs(EXTRACTED_ENTITIES_DIR, exist_ok=True)

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds


def gpt4_vision_entity_extraction(image_path):
    """Send an image to GPT-4 Vision model for entity extraction with retry and backoff logic."""
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
                "max_tokens": 2048,
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

def process_images_with_gpt4():
    """Send all images in the directory to GPT-4 for entity extraction using multithreading."""
    images = [os.path.join(IMAGES_DIR, img) for img in os.listdir(IMAGES_DIR) if img.endswith(".png")]

    # If NUM_FILES is passed, limit the number of files to process
    if NUM_FILES > 0:
        images = images[:NUM_FILES]

    with ThreadPoolExecutor(max_workers=GPT4_THREADS) as executor:
        futures = {executor.submit(gpt4_vision_entity_extraction, img_path): img_path for img_path in images}

        for future in as_completed(futures):
            image_path = futures[future]
            try:
                response = future.result()

                # Debug: Print the raw response before parsing
                print(f"Raw response for image {image_path}: {response}")

                if response:
                    # Ensure that the response is valid JSON before saving
                    try:
                        json_response = json.loads(response)
                    except json.JSONDecodeError as e:
                        print(f"Error: Invalid JSON for image {image_path}. Error: {e}. Skipping this image.")
                        continue
                    
                    # Extract image name (or page number) to name the JSON file
                    img_name = os.path.splitext(os.path.basename(image_path))[0]
                    output_file = os.path.join(EXTRACTED_ENTITIES_DIR, f"extracted_{img_name}.json")
                    
                    # Save the structured response in a separate JSON file for each image
                    with open(output_file, "w") as f:
                        json.dump(json_response, f, indent=4)
                    print(f"Saved entities for {image_path} to {output_file}.")
            except Exception as e:
                print(f"Error processing result for image {image_path}: {e}")

if __name__ == "__main__":
    print("Starting GPT-4 Vision extraction...")
    process_images_with_gpt4()
    print("GPT-4 Vision extraction complete.")
