import os
from pdf2image import convert_from_path
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import save_image
import json

# Load the configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

PDF_PATH = "StyleGuide.pdf"
OUTPUT_DIR = "output_images"
IMAGE_THREADS = config['image_threads']  # Fetch the image thread count

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert_page_to_image(page_num, pdf_path):
    """Converts a specific PDF page to an image and saves it."""
    try:
        images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
        image_path = os.path.join(OUTPUT_DIR, f"page_{page_num}.png")
        save_image(images[0], image_path)
        return f"Page {page_num} converted and saved."
    except Exception as e:
        return f"Error processing page {page_num}: {e}"

def pdf_to_images_multithreaded(pdf_path):
    """Convert all pages of a PDF to images using multiple threads."""
    try:
        first_page_images = convert_from_path(pdf_path, first_page=1, last_page=1)
        num_pages = len(convert_from_path(pdf_path))

        with ThreadPoolExecutor(max_workers=IMAGE_THREADS) as executor:
            futures = [executor.submit(convert_page_to_image, page_num, pdf_path) for page_num in range(1, num_pages + 1)]

            for future in as_completed(futures):
                print(future.result())

    except Exception as e:
        print(f"Error in multithreaded image extraction: {e}")

if __name__ == "__main__":
    print("Starting PDF to image extraction...")
    pdf_to_images_multithreaded(PDF_PATH)
    print("PDF to image extraction complete.")
