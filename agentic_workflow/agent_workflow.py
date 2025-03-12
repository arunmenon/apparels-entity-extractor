import os
import json
import concurrent.futures
import sys
import time
from .page_classifier import PageClassifierAgent
from .entity_extractor import EntityExtractorAgent
from .context_agent import ContextAgent
from .cypher_generator import CypherGeneratorAgent
from .utils import encode_image

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
        
        # Agent pipeline configuration
        self.agent_pipeline = self.config.get('agent_pipeline', ['classifier', 'extractor', 'context', 'cypher'])
        self.hooks = {
            'pre_process': [],
            'post_classify': [],
            'post_extract': [],
            'post_context': [],
            'post_cypher': [],
            'post_process': []
        }
        
        # Load prompts
        self._load_prompts()
        
        # Initialize agents
        self._initialize_agents()
    
    def _load_prompts(self):
        """Load all necessary prompts from files."""
        prompt_dir = "prompts"
        
        # TOC prompts
        with open(os.path.join(prompt_dir, "toc_system_prompt.txt"), "r") as f:
            self.toc_system_prompt = f.read()
        with open(os.path.join(prompt_dir, "toc_extraction_prompt.txt"), "r") as f:
            self.toc_user_prompt = f.read()
        
        # Standard entity extraction prompts
        with open(os.path.join(prompt_dir, "entity_system_prompt.txt"), "r") as f:
            self.std_system_prompt = f.read()
        with open(os.path.join(prompt_dir, "enhanced_entity_extraction_prompt.txt"), "r") as f:
            self.std_user_prompt = f.read()
    
    def _initialize_agents(self):
        """Initialize all agent components."""
        self.agents = {}
        
        # Create instances only for agents in the pipeline
        if 'classifier' in self.agent_pipeline:
            self.agents['classifier'] = PageClassifierAgent(
                api_key=self.api_key,
                model=self.model
            )
        
        if 'extractor' in self.agent_pipeline:
            self.agents['extractor'] = EntityExtractorAgent(
                api_key=self.api_key,
                model=self.model,
                toc_prompt_system=self.toc_system_prompt,
                toc_prompt_user=self.toc_user_prompt,
                std_prompt_system=self.std_system_prompt,
                std_prompt_user=self.std_user_prompt
            )
        
        if 'context' in self.agent_pipeline:
            self.agents['context'] = ContextAgent(
                context_file=self.config.get('context_file', 'compliance_context.json')
            )
        
        if 'cypher' in self.agent_pipeline:
            self.agents['cypher'] = CypherGeneratorAgent(
                api_key=self.api_key,
                model=self.model
            )
        
        # For backward compatibility
        self.classifier = self.agents.get('classifier')
        self.extractor = self.agents.get('extractor')
        self.context_agent = self.agents.get('context')
        self.cypher_generator = self.agents.get('cypher')
    
    def register_hook(self, hook_point, hook_function):
        """
        Register a hook function to be called at a specific point in the workflow.
        
        Args:
            hook_point (str): The point in the workflow to call the hook ('pre_process', 
                             'post_classify', 'post_extract', 'post_context', 'post_cypher', 'post_process')
            hook_function (callable): A function to call at the specified hook point
        """
        if hook_point in self.hooks:
            self.hooks[hook_point].append(hook_function)
            return True
        return False
    
    def register_agent(self, agent_type, agent_instance):
        """
        Register a custom agent to replace or add to the workflow.
        
        Args:
            agent_type (str): The type of agent ('classifier', 'extractor', 'context', 'cypher')
            agent_instance: An instance of the agent class
        """
        self.agents[agent_type] = agent_instance
        
        # Update direct references for backward compatibility
        if agent_type == 'classifier':
            self.classifier = agent_instance
        elif agent_type == 'extractor':
            self.extractor = agent_instance
        elif agent_type == 'context':
            self.context_agent = agent_instance
        elif agent_type == 'cypher':
            self.cypher_generator = agent_instance
        
        # Update pipeline if needed
        if agent_type not in self.agent_pipeline:
            self.agent_pipeline.append(agent_type)
    
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
    
    def _run_hooks(self, hook_point, **kwargs):
        """Run all registered hooks for a given hook point with the provided arguments."""
        results = []
        for hook_func in self.hooks.get(hook_point, []):
            try:
                result = hook_func(**kwargs)
                results.append(result)
            except Exception as e:
                print(f"Error in {hook_point} hook: {str(e)}")
        return results
    
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
        
        # Run pre-process hooks
        self._run_hooks('pre_process', workflow=self, images=images, total_images=total_images)
        
        page_results = {}
        
        for idx, img_path in enumerate(images, 1):
            page_num = idx  # or extract from filename
            img_name = os.path.splitext(os.path.basename(img_path))[0]
            
            print(f"Processing page {page_num}/{total_images}: {img_path}")
            base64_img = encode_image(img_path)
            
            # Create a data dictionary to track the state through the pipeline
            page_data = {
                'page_num': page_num,
                'img_path': img_path,
                'img_name': img_name,
                'base64_img': base64_img
            }
            
            # Step 1: Classify the page (if in pipeline)
            if 'classifier' in self.agent_pipeline and self.classifier:
                start_time = time.time()
                classification = self.classifier.classify_page(base64_img)
                classify_time = time.time() - start_time
                page_data['classification'] = classification
                print(f"Page {page_num} classified as {classification} in {classify_time:.2f}s")
                
                # Run post-classify hooks
                self._run_hooks('post_classify', workflow=self, page_data=page_data)
            else:
                page_data['classification'] = 'REGULAR'  # Default classification
            
            # Step 2: Extract entities based on classification (if in pipeline)
            if 'extractor' in self.agent_pipeline and self.extractor:
                # Get current context before extraction for context-aware processing
                current_context = self.context_agent.entity_context if self.context_agent else {}
                
                start_time = time.time()
                # Extract entities with context awareness
                extracted_data = self.extractor.extract_entities(
                    page_data['classification'], base64_img, context=current_context
                )
                extract_time = time.time() - start_time
                
                # Add page name to extraction data for use in normalization
                extracted_data["_page_name"] = img_name
                
                # Enrich extraction with context when needed
                if 'context' in self.agent_pipeline and self.context_agent:
                    from .enhanced_extractor import enrich_extraction_with_context
                    enriched_data = enrich_extraction_with_context(extracted_data, current_context)
                    # If the enriched data differs from the original extraction, use it instead
                    if enriched_data != extracted_data:
                        print(f"Enhanced extraction results for page {page_num} with context information")
                        extracted_data = enriched_data
                
                # Remove temporary page name field before saving
                if "_page_name" in extracted_data:
                    del extracted_data["_page_name"]
                
                page_data['extracted_data'] = extracted_data
                print(f"Extracted entities from page {page_num} in {extract_time:.2f}s")
                
                # Save extracted data for reference
                output_file = os.path.join(self.extracted_dir, f"extracted_{img_name}.json")
                with open(output_file, "w") as f:
                    json.dump(extracted_data, f, indent=4)
                
                # Run post-extract hooks
                self._run_hooks('post_extract', workflow=self, page_data=page_data)
            
            # Step 3: Update context with extracted data (if in pipeline)
            if 'context' in self.agent_pipeline and self.context_agent:
                start_time = time.time()
                updated_context = self.context_agent.process_extracted_data(
                    page_num, page_data.get('extracted_data', {})
                )
                context_time = time.time() - start_time
                page_data['updated_context'] = updated_context
                print(f"Updated context for page {page_num} in {context_time:.2f}s")
                
                # Run post-context hooks
                self._run_hooks('post_context', workflow=self, page_data=page_data)
            
            # Step 4 (Optional): Generate incremental Cypher query for this page (if in pipeline)
            if 'cypher' in self.agent_pipeline and self.cypher_generator and self.config.get("generate_incremental_cypher", True):
                start_time = time.time()
                incremental_cypher = self.cypher_generator.build_incremental_cypher(
                    page_data.get('updated_context', {}), 
                    page_data.get('extracted_data', {}), 
                    page_num
                )
                cypher_time = time.time() - start_time
                page_data['incremental_cypher'] = incremental_cypher
                
                # Save incremental Cypher
                incremental_file = os.path.join(self.incremental_dir, f"cypher_{img_name}.json")
                with open(incremental_file, "w") as f:
                    json.dump(incremental_cypher, f, indent=4)
                
                print(f"Generated incremental Cypher for page {page_num} in {cypher_time:.2f}s")
                
                # Run post-cypher hooks
                self._run_hooks('post_cypher', workflow=self, page_data=page_data)
            
            # Store page results
            page_results[page_num] = page_data
            
            print(f"Completed page {page_num}/{total_images} - {(idx/total_images)*100:.1f}% done")
        
        # Final steps after all pages are processed
        final_results = {'page_results': page_results}
        
        # Finalize context (if in pipeline)
        if 'context' in self.agent_pipeline and self.context_agent:
            print("Finalizing context...")
            final_context = self.context_agent.finalize_context()
            final_results['final_context'] = final_context
        
        # Generate final Cypher query (if in pipeline)
        if 'cypher' in self.agent_pipeline and self.cypher_generator:
            print("Generating final Cypher query...")
            final_cypher = self.cypher_generator.build_cypher(
                self.context_agent.entity_context if self.context_agent else {}
            )
            final_results['final_cypher'] = final_cypher
            
            # Save final Cypher query
            with open("final_cypher.json", "w") as f:
                json.dump(final_cypher, f, indent=4)
        
        # Run post-process hooks
        self._run_hooks('post_process', workflow=self, final_results=final_results)
        
        print("Workflow complete. Final Cypher saved to final_cypher.json.")
        
        # Return the final Cypher query for backward compatibility
        return final_results.get('final_cypher', {})
    
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
        
        # Run pre-process hooks
        self._run_hooks('pre_process', workflow=self, images=images, total_images=total_images)
        
        page_results = {}
        
        # Step 1: Process the first page serially to establish the primary category
        if total_images > 0 and 'classifier' in self.agent_pipeline and 'extractor' in self.agent_pipeline:
            print("Processing first page serially to establish primary category...")
            first_image = images[0]
            img_name = os.path.splitext(os.path.basename(first_image))[0]
            page_num = 1
            
            base64_img = encode_image(first_image)
            
            # Create page data dictionary for the first page
            first_page_data = {
                'page_num': page_num,
                'img_path': first_image,
                'img_name': img_name,
                'base64_img': base64_img
            }
            
            # Classify first page
            if self.classifier:
                classification = self.classifier.classify_page(base64_img)
                first_page_data['classification'] = classification
                print(f"First page classified as {classification}")
                
                # Run post-classify hooks
                self._run_hooks('post_classify', workflow=self, page_data=first_page_data)
            else:
                first_page_data['classification'] = 'REGULAR'
            
            # Extract entities
            if self.extractor:
                extracted_data = self.extractor.extract_entities(first_page_data['classification'], base64_img)
                first_page_data['extracted_data'] = extracted_data
                
                # Save extracted data
                output_file = os.path.join(self.extracted_dir, f"extracted_{img_name}.json")
                with open(output_file, "w") as f:
                    json.dump(extracted_data, f, indent=4)
                
                # Run post-extract hooks
                self._run_hooks('post_extract', workflow=self, page_data=first_page_data)
            
            # Update context
            if 'context' in self.agent_pipeline and self.context_agent:
                updated_context = self.context_agent.process_extracted_data(
                    page_num, first_page_data.get('extracted_data', {})
                )
                first_page_data['updated_context'] = updated_context
                
                # Run post-context hooks
                self._run_hooks('post_context', workflow=self, page_data=first_page_data)
            
            # Generate incremental Cypher if enabled
            if 'cypher' in self.agent_pipeline and self.cypher_generator and self.config.get("generate_incremental_cypher", True):
                incremental_cypher = self.cypher_generator.build_incremental_cypher(
                    first_page_data.get('updated_context', {}),
                    first_page_data.get('extracted_data', {}),
                    page_num
                )
                first_page_data['incremental_cypher'] = incremental_cypher
                
                incremental_file = os.path.join(self.incremental_dir, f"cypher_{img_name}.json")
                with open(incremental_file, "w") as f:
                    json.dump(incremental_cypher, f, indent=4)
                
                # Run post-cypher hooks
                self._run_hooks('post_cypher', workflow=self, page_data=first_page_data)
            
            # Store first page results
            page_results[page_num] = first_page_data
            
            print(f"Processed first page to establish context")
        
        # Step 2: Process remaining pages in parallel for classification and extraction
        remaining_images = images[1:] if total_images > 1 else []
        
        if remaining_images:
            # Function to process a single page (classification + extraction only)
            def process_page(img_path):
                img_name = os.path.splitext(os.path.basename(img_path))[0]
                page_num = int(img_name.split("_")[-1]) if "_" in img_name else 0
                
                base64_img = encode_image(img_path)
                
                # Create page data dictionary
                page_data = {
                    'page_num': page_num,
                    'img_path': img_path,
                    'img_name': img_name,
                    'base64_img': base64_img
                }
                
                # Classify
                if 'classifier' in self.agent_pipeline and self.classifier:
                    classification = self.classifier.classify_page(base64_img)
                    page_data['classification'] = classification
                else:
                    page_data['classification'] = 'REGULAR'
                
                # Extract
                if 'extractor' in self.agent_pipeline and self.extractor:
                    extracted_data = self.extractor.extract_entities(page_data['classification'], base64_img)
                    page_data['extracted_data'] = extracted_data
                
                return page_data
            
            # Process remaining pages with parallel execution
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
                future_to_img = {executor.submit(process_page, img_path): img_path for img_path in remaining_images}
                
                for future in concurrent.futures.as_completed(future_to_img):
                    img_path = future_to_img[future]
                    try:
                        page_data = future.result()
                        results.append(page_data)
                        print(f"Completed classification and extraction for page {page_data['page_num']}")
                    except Exception as e:
                        print(f"Error processing {img_path}: {str(e)}")
            
            # Sort results by page number to maintain order for context processing
            results.sort(key=lambda x: x["page_num"])
            
            # Now process context and cypher generation sequentially
            for idx, page_data in enumerate(results, 2):  # Start from 2 since first page was already processed
                page_num = page_data["page_num"]
                img_name = page_data["img_name"]
                
                # Run post-classify and post-extract hooks
                if 'classification' in page_data:
                    self._run_hooks('post_classify', workflow=self, page_data=page_data)
                
                if 'extracted_data' in page_data:
                    # Run post-extract hooks
                    self._run_hooks('post_extract', workflow=self, page_data=page_data)
                    
                    # Save extracted data
                    output_file = os.path.join(self.extracted_dir, f"extracted_{img_name}.json")
                    with open(output_file, "w") as f:
                        json.dump(page_data['extracted_data'], f, indent=4)
                
                # Update context (if in pipeline)
                if 'context' in self.agent_pipeline and self.context_agent and 'extracted_data' in page_data:
                    updated_context = self.context_agent.process_extracted_data(
                        page_num, page_data['extracted_data']
                    )
                    page_data['updated_context'] = updated_context
                    
                    # Run post-context hooks
                    self._run_hooks('post_context', workflow=self, page_data=page_data)
                
                # Generate incremental Cypher if enabled (if in pipeline)
                if 'cypher' in self.agent_pipeline and self.cypher_generator and self.config.get("generate_incremental_cypher", True) and 'extracted_data' in page_data:
                    incremental_cypher = self.cypher_generator.build_incremental_cypher(
                        page_data.get('updated_context', self.context_agent.entity_context if self.context_agent else {}),
                        page_data['extracted_data'],
                        page_num
                    )
                    page_data['incremental_cypher'] = incremental_cypher
                    
                    incremental_file = os.path.join(self.incremental_dir, f"cypher_{img_name}.json")
                    with open(incremental_file, "w") as f:
                        json.dump(incremental_cypher, f, indent=4)
                    
                    # Run post-cypher hooks
                    self._run_hooks('post_cypher', workflow=self, page_data=page_data)
                
                # Store page results
                page_results[page_num] = page_data
                
                print(f"Processed context for page {page_num}/{total_images} - {(idx/total_images)*100:.1f}% done")
        
        # Final steps after all pages are processed
        final_results = {'page_results': page_results}
        
        # Finalize context (if in pipeline)
        if 'context' in self.agent_pipeline and self.context_agent:
            print("Finalizing context...")
            final_context = self.context_agent.finalize_context()
            final_results['final_context'] = final_context
        
        # Generate final Cypher query (if in pipeline)
        if 'cypher' in self.agent_pipeline and self.cypher_generator:
            print("Generating final Cypher query...")
            final_cypher = self.cypher_generator.build_cypher(
                self.context_agent.entity_context if self.context_agent else {}
            )
            final_results['final_cypher'] = final_cypher
            
            # Save final Cypher query
            with open("final_cypher.json", "w") as f:
                json.dump(final_cypher, f, indent=4)
        
        # Run post-process hooks
        self._run_hooks('post_process', workflow=self, final_results=final_results)
        
        print("Workflow complete. Final Cypher saved to final_cypher.json.")
        
        # Return the final Cypher query for backward compatibility
        return final_results.get('final_cypher', {})

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