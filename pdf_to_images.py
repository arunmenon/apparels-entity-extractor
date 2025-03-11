import os
import argparse
import json
from pdf2image import convert_from_path
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import save_image
from dotenv import load_dotenv

# Load environment variables and config
load_dotenv()

# Load the configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Default paths
DEFAULT_PDF_PATH = os.getenv("PDF_PATH", os.path.expanduser("~/Downloads/compliance_document.pdf"))
DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output_images")
IMAGE_THREADS = int(os.getenv("IMAGE_THREADS", config.get('image_threads', 6)))

def convert_page_to_image(page_num, pdf_path, output_dir):
    """Converts a specific PDF page to an image and saves it."""
    try:
        images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
        image_path = os.path.join(output_dir, f"page_{page_num}.png")
        save_image(images[0], image_path)
        return f"Page {page_num} converted and saved to {image_path}."
    except Exception as e:
        return f"Error processing page {page_num}: {e}"

def pdf_to_images_multithreaded(pdf_path, output_dir, num_threads=None):
    """Convert all pages of a PDF to images using multiple threads."""
    try:
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Use provided thread count or fall back to config value
        threads = num_threads if num_threads else IMAGE_THREADS
        
        # Get the page count
        num_pages = len(convert_from_path(pdf_path))
        print(f"Found {num_pages} pages in {pdf_path}")

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(convert_page_to_image, page_num, pdf_path, output_dir) 
                      for page_num in range(1, num_pages + 1)]

            for future in as_completed(futures):
                print(future.result())
                
        return num_pages

    except Exception as e:
        print(f"Error in multithreaded image extraction: {e}")
        return 0

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Convert PDF to images for compliance entity extraction')
    
    parser.add_argument('--pdf', '-p', dest='pdf_path', type=str, default=DEFAULT_PDF_PATH,
                        help=f'Path to the PDF file (default: {DEFAULT_PDF_PATH})')
    
    parser.add_argument('--output', '-o', dest='output_dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help=f'Output directory for images (default: {DEFAULT_OUTPUT_DIR})')
    
    parser.add_argument('--threads', '-t', dest='threads', type=int, default=IMAGE_THREADS,
                        help=f'Number of threads for parallel processing (default: {IMAGE_THREADS})')
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()
    
    print(f"Starting PDF to image extraction...")
    print(f"PDF: {args.pdf_path}")
    print(f"Output directory: {args.output_dir}")
    print(f"Threads: {args.threads}")
    
    # Process the PDF
    num_pages = pdf_to_images_multithreaded(args.pdf_path, args.output_dir, args.threads)
    
    print(f"PDF to image extraction complete. Converted {num_pages} pages.")
