import os
import json
import concurrent.futures
import sys
import time
from .page_classifier import PageClassifierAgent
from .entity_extractor import EntityExtractorAgent
from .context_agent import ContextAgent
from .cypher_generator import CypherGeneratorAgent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import encode_image

class AgentWorkflow:
    """Main orchestrator for the agentic workflow pipeline."""
    
    def __init__(self, config_path="config.json"):
        # Load configuration
        with open(config_path, "r") as config_file:
            self.config = json.load(config_file)
        
        # Set up API key and model
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.model = self.config.get('api_model', 'gpt-4-vision-preview')
        self.threads = self.config.get('gpt4_threads', 4)
        
        # Set up directories
        self.images_dir = "output_images"
        self.extracted_dir = "extracted_entities"
        self.incremental_dir = "incremental_cypher"
        
        # Ensure output directories exist
        os.makedirs(self.extracted_dir, exist_ok=True)
        os.makedirs(self.incremental_dir, exist_ok=True)
        
        # Load prompts
        self._load_prompts()
        
        # Initialize agents
        self._initialize_agents()
    
    def _load_prompts(self):
        """Load all necessary prompts from files."""
        # TOC prompts
        with open("toc_system_prompt.txt", "r") as f:
            self.toc_system_prompt = f.read()
        with open("toc_extraction_prompt.txt", "r") as f:
            self.toc_user_prompt = f.read()
        
        # Standard entity extraction prompts
        with open("entity_system_prompt.txt", "r") as f:
            self.std_system_prompt = f.read()
        with open("entity_extraction_prompt.txt", "r") as f:
            self.std_user_prompt = f.read()
    
    def _initialize_agents(self):
        """Initialize all agent components."""
        self.classifier = PageClassifierAgent(
            api_key=self.api_key,
            model=self.model
        )
        
        self.extractor = EntityExtractorAgent(
            api_key=self.api_key,
            model=self.model,
            toc_prompt_system=self.toc_system_prompt,
            toc_prompt_user=self.toc_user_prompt,
            std_prompt_system=self.std_system_prompt,
            std_prompt_user=self.std_user_prompt
        )
        
        self.context_agent = ContextAgent(context_file="compliance_context.json")
        
        self.cypher_generator = CypherGeneratorAgent()
    
    def _get_sorted_images(self):
        """Get a sorted list of images by page number."""
        # Get a sorted list of images to ensure we process them in order by page number
        # Only include files that start with "page_" to avoid processing other images
        images = [os.path.join(self.images_dir, img) for img in os.listdir(self.images_dir) 
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
        return images
    
    def process_images_sequential(self, limit=None):
        """
        Process all images sequentially through the full pipeline.
        
        Args:
            limit: Optional limit on number of images to process
        """
        # Get sorted images
        images = self._get_sorted_images()
        
        # Limit if requested
        if limit and limit > 0:
            images = images[:limit]
        
        total_images = len(images)
        print(f"Starting to process {total_images} pages sequentially...")
        
        for idx, img_path in enumerate(images, 1):
            page_num = idx  # or extract from filename
            img_name = os.path.splitext(os.path.basename(img_path))[0]
            
            print(f"Processing page {page_num}/{total_images}: {img_path}")
            base64_img = encode_image(img_path)
            
            # Step 1: Classify the page
            start_time = time.time()
            classification = self.classifier.classify_page(base64_img)
            classify_time = time.time() - start_time
            print(f"Page {page_num} classified as {classification} in {classify_time:.2f}s")
            
            # Step 2: Extract entities based on classification
            start_time = time.time()
            extracted_data = self.extractor.extract_entities(classification, base64_img)
            extract_time = time.time() - start_time
            print(f"Extracted entities from page {page_num} in {extract_time:.2f}s")
            
            # Save extracted data for reference
            output_file = os.path.join(self.extracted_dir, f"extracted_{img_name}.json")
            with open(output_file, "w") as f:
                json.dump(extracted_data, f, indent=4)
            
            # Step 3: Update context with extracted data
            start_time = time.time()
            updated_context = self.context_agent.process_extracted_data(page_num, extracted_data)
            context_time = time.time() - start_time
            print(f"Updated context for page {page_num} in {context_time:.2f}s")
            
            # Step 4 (Optional): Generate incremental Cypher query for this page
            if self.config.get("generate_incremental_cypher", True):
                start_time = time.time()
                incremental_cypher = self.cypher_generator.build_incremental_cypher(
                    updated_context, extracted_data, page_num
                )
                cypher_time = time.time() - start_time
                
                # Save incremental Cypher
                incremental_file = os.path.join(self.incremental_dir, f"cypher_{img_name}.json")
                with open(incremental_file, "w") as f:
                    json.dump(incremental_cypher, f, indent=4)
                
                print(f"Generated incremental Cypher for page {page_num} in {cypher_time:.2f}s")
            
            print(f"Completed page {page_num}/{total_images} - {(idx/total_images)*100:.1f}% done")
            
        # Final step: Generate complete Cypher query after all pages are processed
        print("Finalizing context...")
        self.context_agent.finalize_context()
        
        print("Generating final Cypher query...")
        final_cypher = self.cypher_generator.build_cypher(self.context_agent.entity_context)
        
        # Save final Cypher query
        with open("final_cypher.json", "w") as f:
            json.dump(final_cypher, f, indent=4)
        
        print("Workflow complete. Final Cypher saved to final_cypher.json.")
        return final_cypher
    
    def process_images_parallel(self, limit=None):
        """
        Process images with parallel execution of classification and extraction.
        Context integration and Cypher generation remain sequential for consistency.
        
        Args:
            limit: Optional limit on number of images to process
        """
        # Get sorted images
        images = self._get_sorted_images()
        
        # Limit if requested
        if limit and limit > 0:
            images = images[:limit]
        
        total_images = len(images)
        print(f"Starting to process {total_images} pages with parallel classification and extraction...")
        
        # Step 1: Process the first page serially to establish the primary category
        if total_images > 0:
            print("Processing first page serially to establish primary category...")
            first_image = images[0]
            img_name = os.path.splitext(os.path.basename(first_image))[0]
            page_num = 1
            
            base64_img = encode_image(first_image)
            
            # Classify first page
            classification = self.classifier.classify_page(base64_img)
            print(f"First page classified as {classification}")
            
            # Extract entities
            extracted_data = self.extractor.extract_entities(classification, base64_img)
            
            # Save extracted data
            output_file = os.path.join(self.extracted_dir, f"extracted_{img_name}.json")
            with open(output_file, "w") as f:
                json.dump(extracted_data, f, indent=4)
            
            # Update context
            self.context_agent.process_extracted_data(page_num, extracted_data)
            
            # Generate incremental Cypher if enabled
            if self.config.get("generate_incremental_cypher", True):
                incremental_cypher = self.cypher_generator.build_incremental_cypher(
                    self.context_agent.entity_context, extracted_data, page_num
                )
                
                incremental_file = os.path.join(self.incremental_dir, f"cypher_{img_name}.json")
                with open(incremental_file, "w") as f:
                    json.dump(incremental_cypher, f, indent=4)
            
            print(f"Processed first page to establish context")
        
        # Step 2: Process remaining pages in parallel for classification and extraction
        remaining_images = images[1:] if total_images > 1 else []
        
        if remaining_images:
            # Function to process a single page (classification + extraction only)
            def process_page(img_path):
                img_name = os.path.splitext(os.path.basename(img_path))[0]
                page_num = int(img_name.split("_")[-1]) if "_" in img_name else 0
                
                base64_img = encode_image(img_path)
                
                # Classify
                classification = self.classifier.classify_page(base64_img)
                
                # Extract
                extracted_data = self.extractor.extract_entities(classification, base64_img)
                
                return {
                    "img_path": img_path,
                    "img_name": img_name,
                    "page_num": page_num,
                    "classification": classification,
                    "extracted_data": extracted_data
                }
            
            # Process remaining pages with parallel execution
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
                future_to_img = {executor.submit(process_page, img_path): img_path for img_path in remaining_images}
                
                for future in concurrent.futures.as_completed(future_to_img):
                    img_path = future_to_img[future]
                    try:
                        result = future.result()
                        results.append(result)
                        print(f"Completed classification and extraction for page {result['page_num']}")
                    except Exception as e:
                        print(f"Error processing {img_path}: {str(e)}")
            
            # Sort results by page number to maintain order for context processing
            results.sort(key=lambda x: x["page_num"])
            
            # Now process context and cypher generation sequentially
            for idx, result in enumerate(results, 2):  # Start from 2 since first page was already processed
                page_num = result["page_num"]
                img_name = result["img_name"]
                extracted_data = result["extracted_data"]
                
                # Save extracted data
                output_file = os.path.join(self.extracted_dir, f"extracted_{img_name}.json")
                with open(output_file, "w") as f:
                    json.dump(extracted_data, f, indent=4)
                
                # Update context
                self.context_agent.process_extracted_data(page_num, extracted_data)
                
                # Generate incremental Cypher if enabled
                if self.config.get("generate_incremental_cypher", True):
                    incremental_cypher = self.cypher_generator.build_incremental_cypher(
                        self.context_agent.entity_context, extracted_data, page_num
                    )
                    
                    incremental_file = os.path.join(self.incremental_dir, f"cypher_{img_name}.json")
                    with open(incremental_file, "w") as f:
                        json.dump(incremental_cypher, f, indent=4)
                
                print(f"Processed context for page {page_num}/{total_images} - {(idx/total_images)*100:.1f}% done")
        
        # Final step: Generate complete Cypher query after all pages are processed
        print("Finalizing context...")
        self.context_agent.finalize_context()
        
        print("Generating final Cypher query...")
        final_cypher = self.cypher_generator.build_cypher(self.context_agent.entity_context)
        
        # Save final Cypher query
        with open("final_cypher.json", "w") as f:
            json.dump(final_cypher, f, indent=4)
        
        print("Workflow complete. Final Cypher saved to final_cypher.json.")
        return final_cypher

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Agentic workflow for compliance document processing')
    parser.add_argument('--limit', type=int, default=-1, help='Limit the number of pages to process')
    parser.add_argument('--sequential', action='store_true', help='Process pages sequentially instead of in parallel')
    args = parser.parse_args()
    
    # Initialize workflow
    workflow = AgentWorkflow()
    
    # Process images based on arguments
    if args.sequential:
        workflow.process_images_sequential(limit=args.limit if args.limit > 0 else None)
    else:
        workflow.process_images_parallel(limit=args.limit if args.limit > 0 else None)