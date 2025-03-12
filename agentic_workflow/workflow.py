"""
Primary workflow orchestrator for agent-based entity extraction.

This module provides the main workflow class that coordinates the agent pipeline,
manages data flow, and handles the processing lifecycle.
"""

import os
import json
import time
import concurrent.futures
from typing import Any, Dict, List, Optional, Callable, Set, Tuple, Union

from .agent_base import Agent, Subject, Observer
from .agent_factory import AgentFactory


class EventTypes:
    """Constants for workflow event types."""
    
    # Workflow-level events
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    PAGE_START = "page_start"
    PAGE_END = "page_end"
    
    # Agent-specific events
    PRE_PROCESS = "pre_process"
    POST_CLASSIFY = "post_classify"
    POST_EXTRACT = "post_extract"
    POST_CONTEXT = "post_context"
    POST_CYPHER = "post_cypher"
    POST_PROCESS = "post_process"


class WorkflowContext:
    """
    Context object for sharing data across the workflow.
    
    This class maintains the global state of the workflow and
    provides access to configuration and shared resources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the workflow context.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.entity_context = {}
        self.page_results = {}
        self.start_time = time.time()
        self.global_state = {}
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with an optional default."""
        return self.config.get(key, default)
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a value in the global state."""
        self.global_state[key] = value
        
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a value from the global state with an optional default."""
        return self.global_state.get(key, default)
    
    def add_page_result(self, page_num: int, result: Dict[str, Any]) -> None:
        """Add page processing result to the context."""
        self.page_results[page_num] = result
        
    def get_page_result(self, page_num: int) -> Optional[Dict[str, Any]]:
        """Get a specific page's processing result."""
        return self.page_results.get(page_num)
    
    def get_execution_time(self) -> float:
        """Get the total execution time in seconds."""
        return time.time() - self.start_time


class AgenticWorkflow(Subject):
    """
    Main orchestrator for agent-based workflows.
    
    This class implements the Observer pattern (as a Subject) and
    the Chain of Responsibility pattern through its agent pipeline.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the agentic workflow.
        
        Args:
            config_path: Path to the configuration file
        """
        super().__init__()  # Initialize Subject
        
        # Load configuration
        with open(config_path, "r") as config_file:
            self.config = json.load(config_file)
        
        # Initialize API credentials
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.model = self.config.get('api_model', 'gpt-4-vision-preview')
        self.threads = self.config.get('parallel_threads', 4)
        
        # Set up directories
        self.images_dir = self.config.get('images_dir', "output_images")
        self.extracted_dir = self.config.get('extracted_dir', "extracted_entities")
        self.incremental_dir = self.config.get('incremental_dir', "incremental_cypher")
        
        # Ensure output directories exist
        os.makedirs(self.extracted_dir, exist_ok=True)
        os.makedirs(self.incremental_dir, exist_ok=True)
        
        # Create workflow context
        self.context = WorkflowContext(self.config)
        
        # Set up agent pipeline
        self.agent_pipeline = self.config.get('agent_pipeline', ['classifier', 'extractor', 'context', 'cypher'])
        
        # Load prompts
        self._load_prompts()
        
        # Initialize agents using factory
        self._initialize_agents()
        
        # Register built-in hooks
        self._register_builtin_hooks()
    
    def _load_prompts(self):
        """Load all necessary prompts from files."""
        prompt_files = {
            'toc_system_prompt': "toc_system_prompt.txt",
            'toc_user_prompt': "toc_extraction_prompt.txt",
            'std_system_prompt': "entity_system_prompt.txt",
            'std_user_prompt': "entity_extraction_prompt.txt",
            'cypher_prompt': "cypher_generator_prompt.txt"
        }
        
        self.prompts = {}
        for key, filename in prompt_files.items():
            try:
                with open(filename, "r") as f:
                    self.prompts[key] = f.read()
            except FileNotFoundError:
                print(f"Warning: Prompt file {filename} not found")
                self.prompts[key] = ""
    
    def _initialize_agents(self):
        """Initialize all agents using the factory pattern."""
        # Create agent configs
        agent_configs = {
            'classifier': {
                'api_key': self.api_key,
                'model': self.model
            },
            'extractor': {
                'api_key': self.api_key,
                'model': self.model,
                'toc_prompt_system': self.prompts.get('toc_system_prompt', ''),
                'toc_prompt_user': self.prompts.get('toc_user_prompt', ''),
                'std_prompt_system': self.prompts.get('std_system_prompt', ''),
                'std_prompt_user': self.prompts.get('std_user_prompt', '')
            },
            'docling_extractor': {
                'api_key': self.api_key, 
                'model': self.model
            },
            'context': {
                'context_file': self.config.get('context_file', 'compliance_context.json')
            },
            'cypher': {
                'api_key': self.api_key,
                'model': self.model,
                'prompt_path': "cypher_generator_prompt.txt"
            }
        }
        
        # Initialize required agents from pipeline
        self.agents = {}
        
        # Check if we should use Docling-based extraction
        use_docling = self.config.get('use_docling', False)
        if use_docling:
            print("Using Docling-based entity extraction")
            # Replace 'extractor' with 'docling_extractor' in the pipeline
            self.agent_pipeline = [
                'docling_extractor' if agent_type == 'extractor' else agent_type 
                for agent_type in self.agent_pipeline
            ]
        
        # Initialize agents based on the pipeline
        for agent_type in self.agent_pipeline:
            try:
                config = agent_configs.get(agent_type, {})
                self.agents[agent_type] = AgentFactory.create(agent_type, config)
            except ValueError as e:
                print(f"Warning: Could not create agent '{agent_type}': {e}")
                
                # If docling_extractor fails, fall back to standard extractor
                if agent_type == 'docling_extractor':
                    print("Falling back to standard entity extractor")
                    self.agent_pipeline = [
                        'extractor' if a_type == 'docling_extractor' else a_type 
                        for a_type in self.agent_pipeline
                    ]
                    if 'extractor' not in self.agents:
                        try:
                            config = agent_configs.get('extractor', {})
                            self.agents['extractor'] = AgentFactory.create('extractor', config)
                        except ValueError as e2:
                            print(f"Could not create fallback extractor: {e2}")
    
    def _register_builtin_hooks(self):
        """Register built-in observers/hooks from config."""
        # Check if validation is enabled
        if self.config.get('enable_validation', False):
            from .hooks.validation import ValidationObserver
            validator = ValidationObserver()
            self.attach(validator, EventTypes.POST_EXTRACT)
        
        # Check if statistics gathering is enabled
        if self.config.get('enable_statistics', False):
            from .hooks.statistics import StatisticsObserver
            stats = StatisticsObserver()
            self.attach(stats, EventTypes.WORKFLOW_END)
    
    def register_observer(self, observer: Observer, event_type: str = 'all') -> None:
        """
        Register an observer for workflow events.
        
        Args:
            observer: The observer to register
            event_type: The event type to observe
        """
        self.attach(observer, event_type)
    
    def register_agent(self, agent_type: str, agent: Agent) -> None:
        """
        Register a custom agent in the workflow.
        
        Args:
            agent_type: The type identifier for the agent
            agent: The agent instance
        """
        self.agents[agent_type] = agent
        
        # Update pipeline if needed
        if agent_type not in self.agent_pipeline:
            self.agent_pipeline.append(agent_type)
    
    def get_sorted_images(self) -> List[str]:
        """
        Get a sorted list of images by page number.
        
        Returns:
            List of image paths sorted by page number
        """
        # Get a sorted list of images to ensure we process them in order by page number
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
    
    def process_images(self, limit: Optional[int] = None, sequential: bool = False) -> Dict[str, Any]:
        """
        Process all images through the agent pipeline.
        
        Args:
            limit: Optional limit on number of images to process
            sequential: Whether to process pages sequentially
            
        Returns:
            Dictionary with workflow results
        """
        if sequential:
            return self.process_images_sequential(limit)
        else:
            return self.process_images_parallel(limit)
    
    def process_images_sequential(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Process all images sequentially through the full pipeline.
        
        Args:
            limit: Optional limit on number of images to process
            
        Returns:
            Dictionary with workflow results
        """
        # Get sorted images
        images = self.get_sorted_images()
        
        # Limit if requested
        if limit and limit > 0:
            images = images[:limit]
        
        total_images = len(images)
        print(f"Starting to process {total_images} pages sequentially...")
        
        # Notify workflow start
        self.notify(EventTypes.WORKFLOW_START, {
            "total_images": total_images,
            "images": images,
            "context": self.context
        })
        
        # Process each page sequentially
        for idx, img_path in enumerate(images, 1):
            page_num = idx
            img_name = os.path.splitext(os.path.basename(img_path))[0]
            
            # Prepare page data
            page_data = {
                'page_num': page_num,
                'img_path': img_path,
                'img_name': img_name,
                'total_pages': total_images
            }
            
            # Notify page start
            self.notify(EventTypes.PAGE_START, page_data)
            
            # Process the page through the agent pipeline
            try:
                # Process through each agent in the pipeline
                for agent_type in self.agent_pipeline:
                    if agent_type in self.agents:
                        agent = self.agents[agent_type]
                        # Process data through this agent
                        agent_result = self._process_with_agent(agent_type, agent, page_data)
                        # Update page data with agent results
                        page_data.update(agent_result)
                        
                        # Notify after each agent completes
                        event_type = f"post_{agent_type}"
                        self.notify(event_type, page_data)
                
                # Save page results to context
                self.context.add_page_result(page_num, page_data)
                
                # Notify page end
                self.notify(EventTypes.PAGE_END, page_data)
                
                print(f"Completed page {page_num}/{total_images} - {(idx/total_images)*100:.1f}% done")
                
            except Exception as e:
                print(f"Error processing page {page_num}: {str(e)}")
                page_data['error'] = str(e)
                self.notify("page_error", page_data)
        
        # Process final steps
        final_results = self._finalize_workflow()
        
        # Notify workflow end
        self.notify(EventTypes.WORKFLOW_END, final_results)
        
        print("\nWorkflow complete.")
        return final_results
    
    def process_images_parallel(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Process images with parallel execution where possible.
        
        Args:
            limit: Optional limit on number of images to process
            
        Returns:
            Dictionary with workflow results
        """
        # Get sorted images
        images = self.get_sorted_images()
        
        # Limit if requested
        if limit and limit > 0:
            images = images[:limit]
        
        total_images = len(images)
        print(f"Starting to process {total_images} pages with parallelization...")
        
        # Notify workflow start
        self.notify(EventTypes.WORKFLOW_START, {
            "total_images": total_images,
            "images": images,
            "context": self.context
        })
        
        # Check for special first page processing
        first_page_serial = self.config.get("first_page_serial", True)
        toc_page_index = self.config.get("toc_page_index", 0)
        
        # Process first/TOC page serially if configured and available
        if first_page_serial and total_images > toc_page_index:
            toc_image = images[toc_page_index]
            toc_name = os.path.splitext(os.path.basename(toc_image))[0]
            toc_page_num = toc_page_index + 1
            
            print(f"Processing page {toc_page_num} serially to establish context...")
            
            # Prepare TOC page data
            toc_page_data = {
                'page_num': toc_page_num,
                'img_path': toc_image,
                'img_name': toc_name,
                'total_pages': total_images,
                'is_toc_page': True
            }
            
            # Notify TOC page start
            self.notify(EventTypes.PAGE_START, toc_page_data)
            
            # Process TOC page through the full pipeline
            for agent_type in self.agent_pipeline:
                if agent_type in self.agents:
                    agent = self.agents[agent_type]
                    agent_result = self._process_with_agent(agent_type, agent, toc_page_data)
                    toc_page_data.update(agent_result)
                    
                    # Notify after each agent completes
                    event_type = f"post_{agent_type}"
                    self.notify(event_type, toc_page_data)
            
            # Save TOC page results
            self.context.add_page_result(toc_page_num, toc_page_data)
            
            # Notify TOC page end
            self.notify(EventTypes.PAGE_END, toc_page_data)
            
            # Remove the TOC page from images to process in parallel
            remaining_images = [img for i, img in enumerate(images) if i != toc_page_index]
        else:
            # Process all pages in parallel
            remaining_images = images
        
        # Process remaining pages with parallel classification and extraction
        if remaining_images:
            results = self._process_pages_parallel(remaining_images, total_images)
            
            # Process results sequentially through context and cypher agents
            self._process_results_sequential(results, total_images)
        
        # Process final steps
        final_results = self._finalize_workflow()
        
        # Notify workflow end
        self.notify(EventTypes.WORKFLOW_END, final_results)
        
        print("\nWorkflow complete.")
        return final_results
    
    def _process_with_agent(self, agent_type: str, agent: Agent, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process data with a specific agent.
        
        Args:
            agent_type: The type of agent
            agent: The agent instance
            page_data: The page data to process
            
        Returns:
            Results from the agent
        """
        result = {}
        
        try:
            # Different processing based on agent type
            if agent_type == 'classifier':
                if 'base64_img' not in page_data:
                    from utils import encode_image
                    page_data['base64_img'] = encode_image(page_data['img_path'])
                
                start_time = time.time()
                classification = agent.classify_page(page_data['base64_img'])
                classify_time = time.time() - start_time
                
                result['classification'] = classification
                result['classify_time'] = classify_time
                print(f"Page {page_data['page_num']} classified as {classification} in {classify_time:.2f}s")
                
            elif agent_type == 'extractor':
                if 'base64_img' not in page_data:
                    from utils import encode_image
                    page_data['base64_img'] = encode_image(page_data['img_path'])
                
                classification = page_data.get('classification', 'REGULAR')
                
                start_time = time.time()
                extracted_data = agent.extract_entities(classification, page_data['base64_img'])
                extract_time = time.time() - start_time
                
                result['extracted_data'] = extracted_data
                result['extract_time'] = extract_time
                print(f"Extracted entities from page {page_data['page_num']} in {extract_time:.2f}s")
                
                # Save extracted data
                output_file = os.path.join(self.extracted_dir, f"extracted_{page_data['img_name']}.json")
                with open(output_file, "w") as f:
                    json.dump(extracted_data, f, indent=4)
                    
            elif agent_type == 'context':
                if 'extracted_data' in page_data:
                    start_time = time.time()
                    updated_context = agent.process_extracted_data(
                        page_data['page_num'], page_data['extracted_data']
                    )
                    context_time = time.time() - start_time
                    
                    result['updated_context'] = updated_context
                    result['context_time'] = context_time
                    print(f"Updated context for page {page_data['page_num']} in {context_time:.2f}s")
                    
            elif agent_type == 'cypher':
                if 'extracted_data' in page_data:
                    # Get context from context agent
                    context_agent = self.agents.get('context')
                    entity_context = context_agent.entity_context if context_agent else {}
                    
                    start_time = time.time()
                    incremental_cypher = agent.build_incremental_cypher(
                        entity_context,
                        page_data['extracted_data'],
                        page_data['page_num']
                    )
                    cypher_time = time.time() - start_time
                    
                    result['incremental_cypher'] = incremental_cypher
                    result['cypher_time'] = cypher_time
                    
                    # Save incremental Cypher
                    incremental_file = os.path.join(
                        self.incremental_dir, 
                        f"cypher_{page_data['img_name']}.json"
                    )
                    with open(incremental_file, "w") as f:
                        json.dump(incremental_cypher, f, indent=4)
                        
                    print(f"Generated incremental Cypher for page {page_data['page_num']} in {cypher_time:.2f}s")
            
            else:
                # For custom agents, use the Agent interface
                result = agent.process(page_data, self.context.global_state)
            
        except Exception as e:
            print(f"Error in {agent_type} agent: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def _process_pages_parallel(self, images: List[str], total_images: int) -> List[Dict[str, Any]]:
        """
        Process classification and extraction in parallel.
        
        Args:
            images: List of image paths to process
            total_images: Total number of images in the workflow
            
        Returns:
            List of page data dictionaries with classification and extraction results
        """
        # Define function for parallel processing
        def process_page(img_path):
            img_name = os.path.splitext(os.path.basename(img_path))[0]
            page_num = int(img_name.split("_")[-1]) if "_" in img_name else 0
            
            # Create page data
            page_data = {
                'page_num': page_num,
                'img_path': img_path,
                'img_name': img_name,
                'total_pages': total_images
            }
            
            # Notify page start
            self.notify(EventTypes.PAGE_START, page_data)
            
            # Process with classifier if available
            if 'classifier' in self.agent_pipeline and 'classifier' in self.agents:
                classifier_result = self._process_with_agent('classifier', self.agents['classifier'], page_data)
                page_data.update(classifier_result)
                
                # Notify after classification
                self.notify(EventTypes.POST_CLASSIFY, page_data)
            else:
                page_data['classification'] = 'REGULAR'
            
            # Process with extractor if available
            if 'extractor' in self.agent_pipeline and 'extractor' in self.agents:
                extractor_result = self._process_with_agent('extractor', self.agents['extractor'], page_data)
                page_data.update(extractor_result)
                
                # Notify after extraction
                self.notify(EventTypes.POST_EXTRACT, page_data)
            
            return page_data
        
        # Process pages in parallel
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            future_to_img = {executor.submit(process_page, img_path): img_path for img_path in images}
            
            for future in concurrent.futures.as_completed(future_to_img):
                img_path = future_to_img[future]
                try:
                    page_data = future.result()
                    results.append(page_data)
                    print(f"Completed classification and extraction for page {page_data['page_num']}")
                except Exception as e:
                    print(f"Error processing {img_path}: {str(e)}")
        
        # Sort results by page number
        results.sort(key=lambda x: x['page_num'])
        return results
    
    def _process_results_sequential(self, results: List[Dict[str, Any]], total_images: int) -> None:
        """
        Process context and cypher generation sequentially.
        
        Args:
            results: Results from parallel processing
            total_images: Total number of images
        """
        # Process each result through context and cypher agents
        for idx, page_data in enumerate(results, 1):
            page_num = page_data['page_num']
            
            # Process with context agent if available
            if 'context' in self.agent_pipeline and 'context' in self.agents and 'extracted_data' in page_data:
                context_result = self._process_with_agent('context', self.agents['context'], page_data)
                page_data.update(context_result)
                
                # Notify after context update
                self.notify(EventTypes.POST_CONTEXT, page_data)
            
            # Process with cypher agent if available
            if 'cypher' in self.agent_pipeline and 'cypher' in self.agents and 'extracted_data' in page_data:
                cypher_result = self._process_with_agent('cypher', self.agents['cypher'], page_data)
                page_data.update(cypher_result)
                
                # Notify after cypher generation
                self.notify(EventTypes.POST_CYPHER, page_data)
            
            # Save page results to context
            self.context.add_page_result(page_num, page_data)
            
            # Notify page end
            self.notify(EventTypes.PAGE_END, page_data)
            
            print(f"Processed context and cypher for page {page_num}/{total_images} - {(idx/total_images)*100:.1f}% done")
    
    def _finalize_workflow(self) -> Dict[str, Any]:
        """
        Finalize the workflow by generating summary data.
        
        Returns:
            Dictionary with final workflow results
        """
        final_results = {
            'page_results': self.context.page_results,
            'execution_time': self.context.get_execution_time()
        }
        
        # Finalize context if available
        if 'context' in self.agents:
            print("Finalizing context...")
            final_context = self.agents['context'].finalize_context()
            final_results['final_context'] = final_context
        
        # Generate final cypher query if available
        if 'cypher' in self.agents and 'context' in self.agents:
            print("Generating final Cypher query...")
            final_cypher = self.agents['cypher'].build_cypher(
                self.agents['context'].entity_context
            )
            final_results['final_cypher'] = final_cypher
            
            # Save final Cypher query
            with open("final_cypher.json", "w") as f:
                json.dump(final_cypher, f, indent=4)
        
        return final_results