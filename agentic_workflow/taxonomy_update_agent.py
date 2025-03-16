"""
Taxonomy Update Agent - An agentic workflow for keeping the taxonomy up to date.

This module implements an agentic workflow to:
1. Monitor for new rules or rule updates
2. Extract entities and concepts from rules
3. Analyze how these entities relate to the existing taxonomy
4. Propose taxonomy updates
5. Validate the updates
6. Integrate the updates into the taxonomy and graph
"""

import json
import os
import logging
from typing import Dict, List, Any, Tuple, Optional

from .agent_base import Agent
from .agent_workflow import AgentWorkflow
from .entity_extractor import EntityExtractor
from .context_agent import ContextAgent
from .cypher_generator import CypherGenerator
from .hooks.validation import validate_extraction

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaxonomyMonitorAgent(Agent):
    """Agent that monitors for new or updated rules that may affect the taxonomy."""
    
    def __init__(self, taxonomy_path: str, rule_heuristics_dir: str, system_prompt_path: str = None, monitoring_prompt_path: str = None):
        """
        Initialize the taxonomy monitor agent.
        
        Args:
            taxonomy_path: Path to the taxonomy JSON file
            rule_heuristics_dir: Directory containing rule heuristic JSON files
            system_prompt_path: Path to system prompt for the LLM
            monitoring_prompt_path: Path to monitoring prompt for the LLM
        """
        super().__init__()
        self.taxonomy_path = taxonomy_path
        self.rule_heuristics_dir = rule_heuristics_dir
        self.taxonomy = self._load_taxonomy()
        
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'taxonomy_monitor_system_prompt.txt')
        self.monitoring_prompt_path = monitoring_prompt_path or os.path.join('prompts', 'taxonomy_monitor_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.monitoring_prompt_path, 'r') as f:
            self.monitoring_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
        
        # Track processed rule IDs
        self.processed_rule_ids_file = os.path.join(os.path.dirname(taxonomy_path), 'processed_rule_ids.json')
        self.processed_rule_ids = self._load_processed_rule_ids()
        
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a taxonomy monitoring assistant specialized in identifying regulatory rules that may affect an apparel and compliance taxonomy.
Your task is to analyze rule heuristics and identify which rules contain entities or concepts that might require updates to the taxonomy.
Focus on rules that introduce new categories, subcategories, or relationships between existing taxonomy elements."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create monitoring prompt if it doesn't exist
        if not os.path.exists(self.monitoring_prompt_path):
            monitoring_prompt = """Analyze the following rule heuristics and identify which rules might affect the taxonomy.

RULE HEURISTICS:
{{rule_heuristics}}

CURRENT TAXONOMY:
{{taxonomy}}

PREVIOUSLY PROCESSED RULE IDs:
{{processed_rule_ids}}

For each rule, determine if it contains entities or concepts that might require updates to the taxonomy.
Consider the following factors:
1. Does the rule introduce new categories or subcategories not present in the taxonomy?
2. Does the rule mention entities that could be added to the taxonomy?
3. Does the rule describe relationships between entities that could enhance the taxonomy?
4. Has this rule been processed before? If so, check if the content has changed significantly.

Return a list of rules to review in JSON format, with each entry containing:
- rule_id: The ID of the rule
- relevance_score: A score between 0 and 1 indicating the rule's relevance to taxonomy updates
- reasoning: A brief explanation of why this rule might affect the taxonomy

Only include rules that have a relevance_score above 0.5."""
            
            with open(self.monitoring_prompt_path, 'w') as f:
                f.write(monitoring_prompt)
    
    def _load_taxonomy(self) -> Dict:
        """Load the current taxonomy from file."""
        with open(self.taxonomy_path, 'r') as f:
            return json.load(f)
    
    def _load_processed_rule_ids(self) -> List[str]:
        """Load the list of processed rule IDs."""
        if os.path.exists(self.processed_rule_ids_file):
            with open(self.processed_rule_ids_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_processed_rule_ids(self, rule_ids: List[str]):
        """Save the list of processed rule IDs."""
        with open(self.processed_rule_ids_file, 'w') as f:
            json.dump(rule_ids, f, indent=2)
    
    def _get_rule_heuristics(self) -> List[Dict]:
        """Get all rule heuristics from the directory."""
        heuristics = []
        for filename in os.listdir(self.rule_heuristics_dir):
            if filename.endswith('_heuristic.json'):
                with open(os.path.join(self.rule_heuristics_dir, filename), 'r') as f:
                    heuristics.append(json.load(f))
        return heuristics
    
    def process(self, input_data: Dict = None) -> Dict:
        """
        Process the taxonomy monitoring task using LLM to identify relevant rules.
        
        Args:
            input_data: Optional input data
            
        Returns:
            Dictionary with new/updated rules that need taxonomy review
        """
        logger.info("Monitoring for rules that may affect taxonomy...")
        
        # Get all rule heuristics
        rule_heuristics = self._get_rule_heuristics()
        
        # If no rule heuristics, return empty result
        if not rule_heuristics:
            return {
                'rules_to_review': [],
                'current_taxonomy': self.taxonomy
            }
        
        # Format data for the prompt
        heuristics_json = json.dumps(rule_heuristics, indent=2)
        taxonomy_json = json.dumps(self.taxonomy, indent=2)
        processed_ids_json = json.dumps(self.processed_rule_ids, indent=2)
        
        # Fill the prompt template
        filled_prompt = (self.monitoring_prompt
                        .replace("{{rule_heuristics}}", heuristics_json)
                        .replace("{{taxonomy}}", taxonomy_json)
                        .replace("{{processed_rule_ids}}", processed_ids_json))
        
        # Use LLM to identify relevant rules
        try:
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4-turbo",  # Use appropriate model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": filled_prompt}
                ],
                temperature=0.2,  # Low temperature for more deterministic results
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the response
            analysis_result = json.loads(llm_response.choices[0].message.content)
            relevant_rules = analysis_result.get('rules_to_review', [])
            
            # Process the relevant rules
            rules_to_review = []
            new_processed_rule_ids = self.processed_rule_ids.copy()
            
            for relevant_rule in relevant_rules:
                rule_id = relevant_rule.get('rule_id')
                
                # Find the corresponding heuristic
                heuristic = next((h for h in rule_heuristics if h.get('rule_id') == rule_id), None)
                
                if heuristic:
                    rules_to_review.append({
                        'rule_id': rule_id,
                        'heuristic': heuristic,
                        'relevance_score': relevant_rule.get('relevance_score', 0.5),
                        'reasoning': relevant_rule.get('reasoning', '')
                    })
                    
                    # Add to processed rule IDs if not already there
                    if rule_id not in new_processed_rule_ids:
                        new_processed_rule_ids.append(rule_id)
            
            # Update processed rule IDs
            if new_processed_rule_ids != self.processed_rule_ids:
                self.processed_rule_ids = new_processed_rule_ids
                self._save_processed_rule_ids(new_processed_rule_ids)
            
            return {
                'rules_to_review': rules_to_review,
                'current_taxonomy': self.taxonomy,
                'llm_analysis': analysis_result  # Include full LLM analysis for transparency
            }
            
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"Error in LLM rule monitoring: {e}")
            
            # Fallback to rule-based approach if LLM processing fails
            logger.warning("Falling back to rule-based monitoring")
            return self._rule_based_monitoring(rule_heuristics)
    
    def _rule_based_monitoring(self, rule_heuristics: List[Dict]) -> Dict:
        """
        Fallback rule-based monitoring if LLM fails.
        
        Args:
            rule_heuristics: List of rule heuristic data
            
        Returns:
            Dictionary with rules to review
        """
        # Identify rules that might need taxonomy updates using simple criteria
        rules_to_review = []
        new_processed_rule_ids = self.processed_rule_ids.copy()
        
        for heuristic in rule_heuristics:
            rule_id = heuristic.get('rule_id', 'unknown')
            
            # Skip already processed rules unless forced to reprocess
            if rule_id in self.processed_rule_ids:
                continue
                
            # Check if the rule contains entities or concepts that might affect taxonomy
            if 'entities' in heuristic and heuristic['entities']:
                rules_to_review.append({
                    'rule_id': rule_id,
                    'heuristic': heuristic,
                    'relevance_score': 0.6,  # Default score
                    'reasoning': 'Rule-based fallback: Contains entities'
                })
                
                # Add to processed rule IDs
                if rule_id not in new_processed_rule_ids:
                    new_processed_rule_ids.append(rule_id)
        
        # Update processed rule IDs
        if new_processed_rule_ids != self.processed_rule_ids:
            self.processed_rule_ids = new_processed_rule_ids
            self._save_processed_rule_ids(new_processed_rule_ids)
        
        return {
            'rules_to_review': rules_to_review,
            'current_taxonomy': self.taxonomy
        }


class TaxonomyEntityExtractor(EntityExtractor):
    """Specialized entity extractor focused on taxonomy-relevant entities."""
    
    def __init__(self, system_prompt_path: str = None, extraction_prompt_path: str = None):
        """
        Initialize the taxonomy entity extractor.
        
        Args:
            system_prompt_path: Path to system prompt for the LLM
            extraction_prompt_path: Path to extraction prompt for the LLM
        """
        # Use default entity extractor prompts if none specified
        system_prompt_path = system_prompt_path or os.path.join('prompts', 'entity_system_prompt.txt')
        extraction_prompt_path = extraction_prompt_path or os.path.join('prompts', 'entity_type_detection_prompt.txt')
        
        super().__init__(system_prompt_path, extraction_prompt_path)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Process the input data to extract taxonomy-relevant entities.
        
        Args:
            input_data: Dictionary containing rules to review
            
        Returns:
            Dictionary with extracted entities and concepts
        """
        logger.info("Extracting taxonomy-relevant entities from rules...")
        
        rules_to_review = input_data.get('rules_to_review', [])
        current_taxonomy = input_data.get('current_taxonomy', {})
        
        all_extracted_entities = []
        
        for rule_data in rules_to_review:
            heuristic = rule_data['heuristic']
            
            # Extract entities and concepts from the rule
            # This uses the base EntityExtractor's functionality
            rule_text = heuristic.get('rule_text', '')
            if rule_text:
                extracted = super().process({'text': rule_text})
                
                # Add rule context to the extracted entities
                for entity in extracted.get('entities', []):
                    entity['source_rule_id'] = rule_data['rule_id']
                    all_extracted_entities.append(entity)
        
        return {
            'extracted_entities': all_extracted_entities,
            'current_taxonomy': current_taxonomy,
            'rules_to_review': rules_to_review
        }


class TaxonomyAnalysisAgent(Agent):
    """Agent that analyzes how extracted entities relate to the existing taxonomy."""
    
    def __init__(self, system_prompt_path: str = None, analysis_prompt_path: str = None):
        """
        Initialize the taxonomy analysis agent.
        
        Args:
            system_prompt_path: Path to system prompt for the LLM
            analysis_prompt_path: Path to analysis prompt for the LLM
        """
        super().__init__()
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'taxonomy_analysis_system_prompt.txt')
        self.analysis_prompt_path = analysis_prompt_path or os.path.join('prompts', 'taxonomy_analysis_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.analysis_prompt_path, 'r') as f:
            self.analysis_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
    
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a taxonomy analyst specialized in analyzing apparel and compliance categories.
Your task is to analyze extracted entities from regulatory rules and determine how they relate to an existing taxonomy.
You will identify if an entity represents a new category or a new subcategory within an existing category.
Be precise in your analysis and consider the hierarchical relationships in the taxonomy."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create analysis prompt if it doesn't exist
        if not os.path.exists(self.analysis_prompt_path):
            analysis_prompt = """Analyze the following entities extracted from regulatory rules against the existing taxonomy.

EXTRACTED ENTITIES:
{{entities}}

CURRENT TAXONOMY:
{{taxonomy}}

For each entity, determine if it represents:
1. A new category that doesn't exist in the taxonomy
2. A new subcategory that should be added to an existing category
3. An entity that already exists in the taxonomy

For each entity, provide the following details in JSON format:
- entity_name: The name of the entity
- entity_type: The type of the entity
- update_type: Either "new_category", "new_subcategory", or "existing"
- category: If a subcategory, which category it belongs to
- confidence: A score between 0 and 1 indicating your confidence in this classification
- source_rule_id: The ID of the rule this entity was extracted from
- reasoning: A brief explanation of your classification decision

Your analysis should be thorough and consider the semantic relationships between entities and categories."""
            
            with open(self.analysis_prompt_path, 'w') as f:
                f.write(analysis_prompt)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Analyze extracted entities against the existing taxonomy using LLM.
        
        Args:
            input_data: Dictionary with extracted entities and current taxonomy
            
        Returns:
            Dictionary with taxonomy analysis results
        """
        logger.info("Analyzing entities against existing taxonomy...")
        
        extracted_entities = input_data.get('extracted_entities', [])
        current_taxonomy = input_data.get('current_taxonomy', {})
        
        # If no entities to analyze, return early
        if not extracted_entities:
            return {
                'taxonomy_updates': [],
                'current_taxonomy': current_taxonomy
            }
        
        # Format entities and taxonomy for the prompt
        entities_json = json.dumps(extracted_entities, indent=2)
        taxonomy_json = json.dumps(current_taxonomy, indent=2)
        
        # Fill the prompt template
        filled_prompt = self.analysis_prompt.replace("{{entities}}", entities_json).replace("{{taxonomy}}", taxonomy_json)
        
        # Call the LLM for analysis
        llm_response = self.llm_client.chat.completions.create(
            model="gpt-4-turbo",  # Use appropriate model
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": filled_prompt}
            ],
            temperature=0.1,  # Low temperature for more deterministic results
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the response
        try:
            analysis_result = json.loads(llm_response.choices[0].message.content)
            taxonomy_updates = analysis_result.get('updates', [])
            
            # Post-process the updates
            processed_updates = []
            for update in taxonomy_updates:
                if update.get('update_type') in ['new_category', 'new_subcategory']:
                    processed_updates.append({
                        'update_type': update.get('update_type'),
                        'category': update.get('category'),
                        'subcategory': update.get('subcategory') if update.get('update_type') == 'new_subcategory' else None,
                        'confidence': update.get('confidence', 0.5),
                        'source_rule_id': update.get('source_rule_id'),
                        'reasoning': update.get('reasoning', '')
                    })
            
            return {
                'taxonomy_updates': processed_updates,
                'current_taxonomy': current_taxonomy,
                'llm_analysis': analysis_result  # Include full LLM analysis for transparency
            }
        
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"Error processing LLM response: {e}")
            
            # Fallback to rule-based analysis if LLM processing fails
            logger.warning("Falling back to rule-based analysis")
            return self._rule_based_analysis(extracted_entities, current_taxonomy)
    
    def _rule_based_analysis(self, extracted_entities: List[Dict], current_taxonomy: Dict) -> Dict:
        """
        Fallback rule-based analysis method if LLM fails.
        
        Args:
            extracted_entities: List of extracted entities
            current_taxonomy: Current taxonomy structure
            
        Returns:
            Dictionary with taxonomy analysis results
        """
        # Map categories and subcategories for easy lookup
        category_map = {}
        for category in current_taxonomy.get('categories', []):
            category_name = category.get('name', '')
            if category_name:
                category_map[category_name.lower()] = {
                    'category': category,
                    'subcategories': {sc.get('name', '').lower(): sc for sc in category.get('subcategories', [])}
                }
        
        # Analyze each extracted entity
        taxonomy_updates = []
        
        for entity in extracted_entities:
            entity_type = entity.get('type', '')
            entity_name = entity.get('name', '')
            
            if not entity_type or not entity_name:
                continue
                
            # Check if this entity type exists in our taxonomy
            entity_type_lower = entity_type.lower()
            entity_exists = False
            
            # Check categories
            if entity_type_lower in category_map:
                entity_exists = True
                # Check if the entity name is a subcategory
                subcategories = category_map[entity_type_lower]['subcategories']
                entity_name_lower = entity_name.lower()
                
                if entity_name_lower not in subcategories:
                    # This might be a new subcategory
                    taxonomy_updates.append({
                        'update_type': 'new_subcategory',
                        'category': entity_type,
                        'subcategory': entity_name,
                        'confidence': 0.7,  # Simplified confidence score
                        'source_rule_id': entity.get('source_rule_id'),
                        'reasoning': 'Rule-based analysis fallback'
                    })
            else:
                # This might be a new category
                taxonomy_updates.append({
                    'update_type': 'new_category',
                    'category': entity_type,
                    'confidence': 0.5,  # Lower confidence for new categories
                    'source_rule_id': entity.get('source_rule_id'),
                    'reasoning': 'Rule-based analysis fallback'
                })
        
        return {
            'taxonomy_updates': taxonomy_updates,
            'current_taxonomy': current_taxonomy
        }


class TaxonomyUpdateProposalAgent(Agent):
    """Agent that generates formal taxonomy update proposals."""
    
    def __init__(self, system_prompt_path: str = None, proposal_prompt_path: str = None):
        """
        Initialize the taxonomy update proposal agent.
        
        Args:
            system_prompt_path: Path to system prompt for the LLM
            proposal_prompt_path: Path to proposal prompt for the LLM
        """
        super().__init__()
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'taxonomy_proposal_system_prompt.txt')
        self.proposal_prompt_path = proposal_prompt_path or os.path.join('prompts', 'taxonomy_proposal_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.proposal_prompt_path, 'r') as f:
            self.proposal_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
    
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a taxonomy proposal generator specialized in creating formal proposals for updating apparel and compliance taxonomies.
Your task is to analyze identified taxonomy updates and generate consolidated, formal proposals for modifying the taxonomy.
You will organize updates by category, consolidate related changes, and create structured proposals that can be easily validated and implemented."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create proposal prompt if it doesn't exist
        if not os.path.exists(self.proposal_prompt_path):
            proposal_prompt = """Generate formal taxonomy update proposals based on the following identified updates.

TAXONOMY UPDATES:
{{taxonomy_updates}}

CURRENT TAXONOMY:
{{current_taxonomy}}

For each set of related updates, create a consolidated formal proposal that outlines:
1. The type of update (new_category or add_subcategories)
2. The category affected
3. Any subcategories to be added
4. A confidence score for the proposal
5. The source rule IDs that led to this proposal
6. A brief justification for the proposal

Group related updates together to avoid redundant or conflicting proposals.
Ensure that each proposal is well-defined, specific, and implementable.

Return a list of formal proposals in JSON format with the following structure:
```json
{
  "update_proposals": [
    {
      "proposal_type": "new_category" or "add_subcategories",
      "category": "Category name",
      "subcategories": ["Subcategory 1", "Subcategory 2", ...],
      "confidence": 0.0-1.0,
      "source_rules": ["rule_id_1", "rule_id_2", ...],
      "justification": "Brief explanation of why this update is proposed"
    },
    ...
  ]
}
```

Only include updates that have a confidence score above 0.4."""
            
            with open(self.proposal_prompt_path, 'w') as f:
                f.write(proposal_prompt)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Generate formal taxonomy update proposals using LLM.
        
        Args:
            input_data: Dictionary with taxonomy analysis results
            
        Returns:
            Dictionary with formal update proposals
        """
        logger.info("Generating formal taxonomy update proposals...")
        
        taxonomy_updates = input_data.get('taxonomy_updates', [])
        current_taxonomy = input_data.get('current_taxonomy', {})
        
        # If no updates to process, return early
        if not taxonomy_updates:
            return {
                'update_proposals': [],
                'current_taxonomy': current_taxonomy
            }
        
        # Format data for the prompt
        updates_json = json.dumps(taxonomy_updates, indent=2)
        taxonomy_json = json.dumps(current_taxonomy, indent=2)
        
        # Fill the prompt template
        filled_prompt = (self.proposal_prompt
                        .replace("{{taxonomy_updates}}", updates_json)
                        .replace("{{current_taxonomy}}", taxonomy_json))
        
        # Call the LLM for generating proposals
        try:
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4-turbo",  # Use appropriate model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": filled_prompt}
                ],
                temperature=0.2,  # Low temperature for more deterministic results
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the response
            proposal_result = json.loads(llm_response.choices[0].message.content)
            update_proposals = proposal_result.get('update_proposals', [])
            
            # Ensure the proposals have all required fields
            for proposal in update_proposals:
                if 'subcategories' not in proposal:
                    proposal['subcategories'] = []
                if 'source_rules' not in proposal:
                    proposal['source_rules'] = []
                if 'confidence' not in proposal:
                    proposal['confidence'] = 0.5
            
            return {
                'update_proposals': update_proposals,
                'current_taxonomy': current_taxonomy,
                'llm_proposals': proposal_result  # Include full LLM proposals for transparency
            }
            
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"Error in LLM proposal generation: {e}")
            
            # Fallback to rule-based approach if LLM processing fails
            logger.warning("Falling back to rule-based proposal generation")
            return self._rule_based_proposals(taxonomy_updates, current_taxonomy)
    
    def _rule_based_proposals(self, taxonomy_updates: List[Dict], current_taxonomy: Dict) -> Dict:
        """
        Fallback rule-based proposal generation if LLM fails.
        
        Args:
            taxonomy_updates: List of taxonomy updates
            current_taxonomy: Current taxonomy structure
            
        Returns:
            Dictionary with update proposals
        """
        # Group updates by category
        updates_by_category = {}
        for update in taxonomy_updates:
            category = update.get('category', '')
            if category:
                if category not in updates_by_category:
                    updates_by_category[category] = []
                updates_by_category[category].append(update)
        
        # Generate consolidated update proposals
        update_proposals = []
        
        for category, updates in updates_by_category.items():
            # Check if this is a new category
            new_category = any(u.get('update_type') == 'new_category' for u in updates)
            
            if new_category:
                # Propose a new category
                subcategories = [u.get('subcategory') for u in updates 
                                if u.get('update_type') == 'new_subcategory' and u.get('subcategory')]
                
                update_proposals.append({
                    'proposal_type': 'new_category',
                    'category': category,
                    'subcategories': subcategories,
                    'confidence': max([u.get('confidence', 0) for u in updates]),
                    'source_rules': list(set([u.get('source_rule_id') for u in updates if u.get('source_rule_id')])),
                    'justification': 'Rule-based proposal fallback: New category identified'
                })
            else:
                # Propose adding subcategories to existing category
                subcategories = [u.get('subcategory') for u in updates 
                                if u.get('update_type') == 'new_subcategory' and u.get('subcategory')]
                
                if subcategories:
                    update_proposals.append({
                        'proposal_type': 'add_subcategories',
                        'category': category,
                        'subcategories': subcategories,
                        'confidence': max([u.get('confidence', 0) for u in updates]),
                        'source_rules': list(set([u.get('source_rule_id') for u in updates if u.get('source_rule_id')])),
                        'justification': 'Rule-based proposal fallback: New subcategories identified'
                    })
        
        return {
            'update_proposals': update_proposals,
            'current_taxonomy': current_taxonomy
        }


class TaxonomyValidationAgent(Agent):
    """Agent that validates taxonomy update proposals."""
    
    def __init__(self, system_prompt_path: str = None, validation_prompt_path: str = None):
        """
        Initialize the taxonomy validation agent.
        
        Args:
            system_prompt_path: Path to system prompt for the LLM
            validation_prompt_path: Path to validation prompt for the LLM
        """
        super().__init__()
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'taxonomy_validation_system_prompt.txt')
        self.validation_prompt_path = validation_prompt_path or os.path.join('prompts', 'taxonomy_validation_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.validation_prompt_path, 'r') as f:
            self.validation_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
    
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a taxonomy validation specialist focused on ensuring the integrity and consistency of apparel and compliance taxonomies.
Your task is to validate proposed taxonomy updates against the existing taxonomy structure.
You will identify any issues that would prevent successful implementation of the proposals, such as duplicates, conflicts, or inconsistencies."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create validation prompt if it doesn't exist
        if not os.path.exists(self.validation_prompt_path):
            validation_prompt = """Validate the following taxonomy update proposals against the current taxonomy.

UPDATE PROPOSALS:
{{update_proposals}}

CURRENT TAXONOMY:
{{current_taxonomy}}

For each proposal, check for the following issues:
1. For new_category proposals:
   - Does the category already exist in the taxonomy?
   - Is the category name valid and consistent with naming conventions?
   - Are the proposed subcategories appropriate for this category?

2. For add_subcategories proposals:
   - Does the parent category exist in the taxonomy?
   - Do any of the proposed subcategories already exist in that category?
   - Are the subcategory names valid and consistent with naming conventions?

3. For all proposals:
   - Are there any naming conflicts or ambiguities?
   - Is the proposal consistent with the overall taxonomy structure?
   - Is the confidence score reasonable for the proposal?

Return a validation report in JSON format with the following structure:
```json
{
  "validated_proposals": [
    {
      // Original proposal contents with any necessary modifications
      "proposal_type": "...",
      "category": "...",
      "subcategories": [...],
      "confidence": X.X,
      "source_rules": [...],
      "justification": "...",
      
      // Added validation fields
      "is_valid": true,
      "validation_issues": []
    },
    ...
  ],
  "rejected_proposals": [
    {
      // Original proposal contents
      "proposal_type": "...",
      "category": "...",
      "subcategories": [...],
      "confidence": X.X,
      "source_rules": [...],
      "justification": "...",
      
      // Added validation fields
      "is_valid": false,
      "validation_issues": ["Reason 1", "Reason 2", ...]
    },
    ...
  ]
}
```

For valid proposals, remove any subcategories that already exist in the taxonomy.
For invalid proposals, provide clear explanations of the issues in the validation_issues array."""
            
            with open(self.validation_prompt_path, 'w') as f:
                f.write(validation_prompt)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Validate taxonomy update proposals using LLM.
        
        Args:
            input_data: Dictionary with update proposals
            
        Returns:
            Dictionary with validated update proposals
        """
        logger.info("Validating taxonomy update proposals...")
        
        update_proposals = input_data.get('update_proposals', [])
        current_taxonomy = input_data.get('current_taxonomy', {})
        
        # If no proposals to validate, return early
        if not update_proposals:
            return {
                'validated_proposals': [],
                'rejected_proposals': [],
                'current_taxonomy': current_taxonomy
            }
        
        # Format data for the prompt
        proposals_json = json.dumps(update_proposals, indent=2)
        taxonomy_json = json.dumps(current_taxonomy, indent=2)
        
        # Fill the prompt template
        filled_prompt = (self.validation_prompt
                        .replace("{{update_proposals}}", proposals_json)
                        .replace("{{current_taxonomy}}", taxonomy_json))
        
        # Call the LLM for validation
        try:
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4-turbo",  # Use appropriate model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": filled_prompt}
                ],
                temperature=0.1,  # Low temperature for more deterministic results
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the response
            validation_result = json.loads(llm_response.choices[0].message.content)
            validated_proposals = validation_result.get('validated_proposals', [])
            rejected_proposals = validation_result.get('rejected_proposals', [])
            
            # Ensure all required fields are present
            for proposal in validated_proposals + rejected_proposals:
                if 'is_valid' not in proposal:
                    proposal['is_valid'] = proposal in validated_proposals
                if 'validation_issues' not in proposal:
                    proposal['validation_issues'] = []
            
            return {
                'validated_proposals': validated_proposals,
                'rejected_proposals': rejected_proposals,
                'current_taxonomy': current_taxonomy,
                'llm_validation': validation_result  # Include full LLM validation for transparency
            }
            
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"Error in LLM validation: {e}")
            
            # Fallback to rule-based validation if LLM processing fails
            logger.warning("Falling back to rule-based validation")
            return self._rule_based_validation(update_proposals, current_taxonomy)
    
    def _rule_based_validation(self, update_proposals: List[Dict], current_taxonomy: Dict) -> Dict:
        """
        Fallback rule-based validation if LLM fails.
        
        Args:
            update_proposals: List of update proposals
            current_taxonomy: Current taxonomy structure
            
        Returns:
            Dictionary with validated proposals
        """
        # Get existing categories
        existing_categories = [c.get('name', '').lower() for c in current_taxonomy.get('categories', [])]
        
        # Validate each proposal
        validated_proposals = []
        rejected_proposals = []
        
        for proposal in update_proposals:
            is_valid = True
            validation_issues = []
            
            proposal_type = proposal.get('proposal_type', '')
            category = proposal.get('category', '')
            
            if not category:
                is_valid = False
                validation_issues.append("Missing category name")
                
                # Add validation results to the proposal
                proposal['is_valid'] = is_valid
                proposal['validation_issues'] = validation_issues
                rejected_proposals.append(proposal)
                continue
                
            category_lower = category.lower()
            
            if proposal_type == 'new_category':
                # Check if category already exists
                if category_lower in existing_categories:
                    is_valid = False
                    validation_issues.append(f"Category '{category}' already exists")
            
            elif proposal_type == 'add_subcategories':
                # Check if category exists
                if category_lower not in existing_categories:
                    is_valid = False
                    validation_issues.append(f"Category '{category}' does not exist")
                else:
                    # Find the category object
                    category_obj = next((c for c in current_taxonomy.get('categories', []) 
                                       if c.get('name', '').lower() == category_lower), None)
                    
                    if category_obj:
                        # Check subcategories
                        existing_subcategories = [sc.get('name', '').lower() for sc in category_obj.get('subcategories', [])]
                        
                        new_subcategories = []
                        for subcategory in proposal.get('subcategories', []):
                            if subcategory.lower() in existing_subcategories:
                                validation_issues.append(f"Subcategory '{subcategory}' already exists in category '{category}'")
                            else:
                                new_subcategories.append(subcategory)
                        
                        if not new_subcategories:
                            is_valid = False
                        else:
                            # Update the proposal with only new subcategories
                            proposal['subcategories'] = new_subcategories
            
            # Add validation results to the proposal
            proposal['is_valid'] = is_valid
            proposal['validation_issues'] = validation_issues
            
            if is_valid:
                validated_proposals.append(proposal)
            else:
                rejected_proposals.append(proposal)
        
        return {
            'validated_proposals': validated_proposals,
            'rejected_proposals': rejected_proposals,
            'current_taxonomy': current_taxonomy
        }


class TaxonomyIntegrationAgent(Agent):
    """Agent that integrates validated taxonomy updates into the taxonomy and graph."""
    
    def __init__(self, taxonomy_path: str, system_prompt_path: str = None, integration_prompt_path: str = None):
        """
        Initialize the taxonomy integration agent.
        
        Args:
            taxonomy_path: Path to the taxonomy JSON file
            system_prompt_path: Path to system prompt for the LLM
            integration_prompt_path: Path to integration prompt for the LLM
        """
        super().__init__()
        self.taxonomy_path = taxonomy_path
        
        # Default to standard prompts if none provided
        self.system_prompt_path = system_prompt_path or os.path.join('prompts', 'taxonomy_integration_system_prompt.txt')
        self.integration_prompt_path = integration_prompt_path or os.path.join('prompts', 'taxonomy_integration_prompt.txt')
        
        # Create and load prompts if they don't exist
        self._ensure_prompts_exist()
        
        # Load prompts
        with open(self.system_prompt_path, 'r') as f:
            self.system_prompt = f.read()
            
        with open(self.integration_prompt_path, 'r') as f:
            self.integration_prompt = f.read()
            
        # Initialize LLM client
        from scripts.client import get_llm_client
        self.llm_client = get_llm_client()
        
        # Initialize CypherGenerator
        self.cypher_generator = CypherGenerator()
    
    def _ensure_prompts_exist(self):
        """Create default prompts if they don't exist."""
        os.makedirs(os.path.dirname(self.system_prompt_path), exist_ok=True)
        
        # Create system prompt if it doesn't exist
        if not os.path.exists(self.system_prompt_path):
            system_prompt = """You are a taxonomy integration specialist responsible for applying validated updates to taxonomy structures.
Your task is to integrate new categories and subcategories into an existing taxonomy while maintaining its integrity and consistency.
You will generate precise update plans including both JSON modifications and graph database Cypher statements."""
            
            with open(self.system_prompt_path, 'w') as f:
                f.write(system_prompt)
        
        # Create integration prompt if it doesn't exist
        if not os.path.exists(self.integration_prompt_path):
            integration_prompt = """Create an integration plan for incorporating the following validated taxonomy updates.

VALIDATED PROPOSALS:
{{validated_proposals}}

CURRENT TAXONOMY:
{{current_taxonomy}}

For each validated proposal, determine exactly how to update the taxonomy structure:
1. For new_category proposals:
   - Define the new category structure with its subcategories
   - Generate appropriate Cypher statements to add this to the graph database

2. For add_subcategories proposals:
   - Identify the existing category to update
   - List the new subcategories to add
   - Generate appropriate Cypher statements to add these to the graph database

Provide your integration plan in JSON format with the following structure:
```json
{
  "updated_taxonomy": {
    // The complete updated taxonomy structure with all changes applied
  },
  "added_items": {
    "categories": ["Category1", "Category2", ...],
    "subcategories": [
      {"category": "Category1", "subcategory": "Subcategory1"},
      {"category": "Category2", "subcategory": "Subcategory2"},
      ...
    ]
  },
  "cypher_statements": [
    "MERGE (c:Category {name: 'Category1'}) ON CREATE SET c.created = timestamp() RETURN c",
    "MATCH (c:Category {name: 'Category1'}) MERGE (s:Subcategory {name: 'Subcategory1'}) ON CREATE SET s.created = timestamp() MERGE (c)-[:CONTAINS]->(s) RETURN c, s",
    ...
  ]
}
```

For the updated_taxonomy field, return the complete modified taxonomy JSON structure with all changes applied.
For the cypher_statements field, provide valid Neo4j Cypher statements that could be executed directly against a graph database."""
            
            with open(self.integration_prompt_path, 'w') as f:
                f.write(integration_prompt)
    
    def process(self, input_data: Dict) -> Dict:
        """
        Integrate validated taxonomy updates using LLM.
        
        Args:
            input_data: Dictionary with validated update proposals
            
        Returns:
            Dictionary with integration results
        """
        logger.info("Integrating taxonomy updates...")
        
        validated_proposals = input_data.get('validated_proposals', [])
        current_taxonomy = input_data.get('current_taxonomy', {})
        
        # If no proposals to integrate, return early
        if not validated_proposals:
            return {
                'updated_taxonomy': current_taxonomy,
                'added_items': {'categories': [], 'subcategories': []},
                'cypher_statements': []
            }
        
        # Format data for the prompt
        proposals_json = json.dumps(validated_proposals, indent=2)
        taxonomy_json = json.dumps(current_taxonomy, indent=2)
        
        # Fill the prompt template
        filled_prompt = (self.integration_prompt
                        .replace("{{validated_proposals}}", proposals_json)
                        .replace("{{current_taxonomy}}", taxonomy_json))
        
        # Call the LLM for integration plan
        try:
            llm_response = self.llm_client.chat.completions.create(
                model="gpt-4-turbo",  # Use appropriate model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": filled_prompt}
                ],
                temperature=0.1,  # Low temperature for more deterministic results
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the response
            integration_result = json.loads(llm_response.choices[0].message.content)
            updated_taxonomy = integration_result.get('updated_taxonomy', current_taxonomy.copy())
            added_items = integration_result.get('added_items', {'categories': [], 'subcategories': []})
            cypher_statements = integration_result.get('cypher_statements', [])
            
            # Save the updated taxonomy
            if updated_taxonomy != current_taxonomy:
                backup_path = f"{self.taxonomy_path}.bak"
                
                # Backup the current taxonomy
                with open(backup_path, 'w') as f:
                    json.dump(current_taxonomy, f, indent=2)
                    
                # Save the updated taxonomy
                with open(self.taxonomy_path, 'w') as f:
                    json.dump(updated_taxonomy, f, indent=2)
            
            return {
                'updated_taxonomy': updated_taxonomy,
                'added_items': added_items,
                'cypher_statements': cypher_statements,
                'llm_integration': integration_result  # Include full LLM integration for transparency
            }
            
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"Error in LLM integration: {e}")
            
            # Fallback to rule-based integration if LLM processing fails
            logger.warning("Falling back to rule-based integration")
            return self._rule_based_integration(validated_proposals, current_taxonomy)
    
    def _rule_based_integration(self, validated_proposals: List[Dict], current_taxonomy: Dict) -> Dict:
        """
        Fallback rule-based integration if LLM fails.
        
        Args:
            validated_proposals: List of validated proposals
            current_taxonomy: Current taxonomy structure
            
        Returns:
            Dictionary with integration results
        """
        # Apply updates to the taxonomy structure
        updated_taxonomy = current_taxonomy.copy()
        
        # Track which categories and subcategories were added
        added_items = {
            'categories': [],
            'subcategories': []
        }
        
        # Apply each validated proposal
        for proposal in validated_proposals:
            proposal_type = proposal.get('proposal_type', '')
            category = proposal.get('category', '')
            
            if proposal_type == 'new_category':
                # Add new category
                new_category = {
                    'name': category,
                    'subcategories': []
                }
                
                # Add subcategories if present
                for subcategory in proposal.get('subcategories', []):
                    new_category['subcategories'].append({
                        'name': subcategory
                    })
                    added_items['subcategories'].append({
                        'category': category,
                        'subcategory': subcategory
                    })
                
                updated_taxonomy['categories'].append(new_category)
                added_items['categories'].append(category)
                
            elif proposal_type == 'add_subcategories':
                # Find the category
                for cat in updated_taxonomy['categories']:
                    if cat.get('name', '') == category:
                        # Add new subcategories
                        for subcategory in proposal.get('subcategories', []):
                            cat['subcategories'].append({
                                'name': subcategory
                            })
                            added_items['subcategories'].append({
                                'category': category,
                                'subcategory': subcategory
                            })
        
        # Generate Cypher statements for graph updates
        cypher_statements = []
        
        # Create statements for new categories
        for category in added_items['categories']:
            cypher_statements.append(
                f"MERGE (c:Category {{name: '{category}'}}) "
                f"ON CREATE SET c.created = timestamp() "
                f"RETURN c"
            )
        
        # Create statements for new subcategories
        for item in added_items['subcategories']:
            category = item['category']
            subcategory = item['subcategory']
            
            cypher_statements.append(
                f"MATCH (c:Category {{name: '{category}'}}) "
                f"MERGE (s:Subcategory {{name: '{subcategory}'}}) "
                f"ON CREATE SET s.created = timestamp() "
                f"MERGE (c)-[:CONTAINS]->(s) "
                f"RETURN c, s"
            )
        
        # Save the updated taxonomy
        if validated_proposals:
            backup_path = f"{self.taxonomy_path}.bak"
            
            # Backup the current taxonomy
            with open(backup_path, 'w') as f:
                json.dump(current_taxonomy, f, indent=2)
                
            # Save the updated taxonomy
            with open(self.taxonomy_path, 'w') as f:
                json.dump(updated_taxonomy, f, indent=2)
        
        return {
            'updated_taxonomy': updated_taxonomy,
            'added_items': added_items,
            'cypher_statements': cypher_statements
        }


class TaxonomyUpdateWorkflow(AgentWorkflow):
    """Workflow for updating the taxonomy based on rule analysis."""
    
    def __init__(self, taxonomy_path: str, rule_heuristics_dir: str, prompts_dir: str = None):
        """
        Initialize the taxonomy update workflow.
        
        Args:
            taxonomy_path: Path to the taxonomy JSON file
            rule_heuristics_dir: Directory containing rule heuristic JSON files
            prompts_dir: Directory containing LLM prompts (defaults to 'prompts')
        """
        super().__init__()
        
        # Set prompts directory
        self.prompts_dir = prompts_dir or 'prompts'
        os.makedirs(self.prompts_dir, exist_ok=True)
        
        # Prepare prompt paths
        monitor_system_prompt = os.path.join(self.prompts_dir, 'taxonomy_monitor_system_prompt.txt')
        monitor_prompt = os.path.join(self.prompts_dir, 'taxonomy_monitor_prompt.txt')
        
        entity_system_prompt = os.path.join(self.prompts_dir, 'entity_system_prompt.txt')
        entity_extraction_prompt = os.path.join(self.prompts_dir, 'entity_type_detection_prompt.txt')
        
        analysis_system_prompt = os.path.join(self.prompts_dir, 'taxonomy_analysis_system_prompt.txt')
        analysis_prompt = os.path.join(self.prompts_dir, 'taxonomy_analysis_prompt.txt')
        
        proposal_system_prompt = os.path.join(self.prompts_dir, 'taxonomy_proposal_system_prompt.txt')
        proposal_prompt = os.path.join(self.prompts_dir, 'taxonomy_proposal_prompt.txt')
        
        validation_system_prompt = os.path.join(self.prompts_dir, 'taxonomy_validation_system_prompt.txt')
        validation_prompt = os.path.join(self.prompts_dir, 'taxonomy_validation_prompt.txt')
        
        integration_system_prompt = os.path.join(self.prompts_dir, 'taxonomy_integration_system_prompt.txt')
        integration_prompt = os.path.join(self.prompts_dir, 'taxonomy_integration_prompt.txt')
        
        # Create the agents with explicit prompts
        self.monitor_agent = TaxonomyMonitorAgent(
            taxonomy_path, 
            rule_heuristics_dir,
            system_prompt_path=monitor_system_prompt,
            monitoring_prompt_path=monitor_prompt
        )
        
        self.entity_extractor = TaxonomyEntityExtractor(
            system_prompt_path=entity_system_prompt,
            extraction_prompt_path=entity_extraction_prompt
        )
        
        self.analysis_agent = TaxonomyAnalysisAgent(
            system_prompt_path=analysis_system_prompt,
            analysis_prompt_path=analysis_prompt
        )
        
        self.proposal_agent = TaxonomyUpdateProposalAgent(
            system_prompt_path=proposal_system_prompt,
            proposal_prompt_path=proposal_prompt
        )
        
        self.validation_agent = TaxonomyValidationAgent(
            system_prompt_path=validation_system_prompt,
            validation_prompt_path=validation_prompt
        )
        
        self.integration_agent = TaxonomyIntegrationAgent(
            taxonomy_path,
            system_prompt_path=integration_system_prompt,
            integration_prompt_path=integration_prompt
        )
        
        # Configure the workflow
        self.add_agent(self.monitor_agent)
        self.add_agent(self.entity_extractor)
        self.add_agent(self.analysis_agent)
        self.add_agent(self.proposal_agent)
        self.add_agent(self.validation_agent)
        self.add_agent(self.integration_agent)
    
    def run(self, input_data: Dict = None) -> Dict:
        """
        Run the taxonomy update workflow.
        
        Args:
            input_data: Optional input data to start the workflow
            
        Returns:
            Dictionary with workflow results
        """
        logger.info("Starting taxonomy update workflow...")
        
        # Run the workflow
        result = super().run(input_data)
        
        logger.info("Taxonomy update workflow completed")
        
        # Format a summary of the results
        summary = {
            'proposals_count': len(result.get('validated_proposals', [])),
            'rejected_count': len(result.get('rejected_proposals', [])),
            'categories_added': len(result.get('added_items', {}).get('categories', [])),
            'subcategories_added': len(result.get('added_items', {}).get('subcategories', []))
        }
        
        result['summary'] = summary
        
        # Include extended information if available
        result['llm_processing'] = {
            'monitor_analysis': result.get('llm_analysis', {}),
            'entity_extraction': result.get('extracted_entities', []),
            'taxonomy_analysis': result.get('llm_analysis', {}),
            'proposal_generation': result.get('llm_proposals', {}),
            'validation': result.get('llm_validation', {}),
            'integration': result.get('llm_integration', {})
        }
        
        return result


# Example usage
if __name__ == "__main__":
    # Configure paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    taxonomy_path = os.path.join(base_dir, 'taxonomy', 'compliance_taxonomy.json')
    rule_heuristics_dir = os.path.join(base_dir, 'parsed_rule_heuristics')
    
    # Create and run the workflow
    workflow = TaxonomyUpdateWorkflow(taxonomy_path, rule_heuristics_dir)
    result = workflow.run()
    
    # Print summary
    print("Taxonomy Update Workflow Results:")
    print(f"Proposals validated: {result['summary']['proposals_count']}")
    print(f"Proposals rejected: {result['summary']['rejected_count']}")
    print(f"Categories added: {result['summary']['categories_added']}")
    print(f"Subcategories added: {result['summary']['subcategories_added']}")