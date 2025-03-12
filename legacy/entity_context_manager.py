import os
import json
import time

class EntityContextManager:
    """Manager for entity context tracking across document pages."""
    
    def __init__(self, context_file="entity_context.json"):
        """Initialize the context manager with a file path for persistent storage."""
        self.context_file = context_file
        self.entity_context = {
            "offensive_content_category": {},  # Map category names to details
            "sub_category": {},                # Map subcategories to parent categories
            "guideline": {},                   # Map guidelines to parent subcategories
            "pending_rules": []                # Rules waiting for parent attachment
        }
        self.load_context()
    
    def load_context(self):
        """Load existing entity context from file if it exists."""
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, 'r') as f:
                    self.entity_context = json.load(f)
                print(f"Loaded existing entity context from {self.context_file}")
            except Exception as e:
                print(f"Error loading entity context: {e}")
        else:
            print("No existing entity context found. Starting with empty context.")
    
    def save_context(self):
        """Save the current entity context to a file."""
        try:
            with open(self.context_file, 'w') as f:
                json.dump(self.entity_context, f, indent=4)
            print(f"Saved entity context to {self.context_file}")
        except Exception as e:
            print(f"Error saving entity context: {e}")
    
    def process_page_extraction(self, page_num, extraction_result):
        """
        Process a page extraction, update context, and handle missing parent entities.
        
        Args:
            page_num: The page number being processed
            extraction_result: The extracted data from this page
            
        Returns:
            Updated extraction_result with inferred parent entities
        """
        # Extract key information
        cypher_query = extraction_result.get('cypher_query', '')
        
        # Handle category normalization - without hardcoding any specific category
        if 'offensive_content_category' in extraction_result:
            category = extraction_result['offensive_content_category'].get('name')
            if category:
                # Check if this is the first category we've seen
                if not self.entity_context['offensive_content_category']:
                    # This is the first category - use it as the primary category
                    self.entity_context['offensive_content_category'][category] = {
                        'last_seen': time.time(),
                        'page': page_num,
                        'is_primary': True
                    }
                    print(f"Page {page_num}: Set primary category '{category}'")
                else:
                    # We already have at least one category
                    # Check if this is a variant of an existing category
                    primary_category = None
                    for existing_cat, info in self.entity_context['offensive_content_category'].items():
                        if info.get('is_primary'):
                            primary_category = existing_cat
                            break
                    
                    if primary_category and category != primary_category:
                        # Similar category detected - normalize to primary
                        print(f"Page {page_num}: Normalizing category '{category}' to primary '{primary_category}'")
                        extraction_result['offensive_content_category']['name'] = primary_category
                        category = primary_category
                        
                        # Add this as an alias for the primary category
                        if 'aliases' not in self.entity_context['offensive_content_category'][primary_category]:
                            self.entity_context['offensive_content_category'][primary_category]['aliases'] = []
                        
                        if category not in self.entity_context['offensive_content_category'][primary_category]['aliases']:
                            self.entity_context['offensive_content_category'][primary_category]['aliases'].append(category)
                    
                    # Update timestamp for this category
                    self.entity_context['offensive_content_category'][category] = {
                        'last_seen': time.time(),
                        'page': page_num,
                        'is_primary': category == primary_category
                    }
                    print(f"Page {page_num}: Updated category '{category}'")
        
        if 'sub_category' in extraction_result:
            subcategory = extraction_result['sub_category'].get('name')
            parent = extraction_result.get('offensive_content_category', {}).get('name')
            
            # If parent category is missing, set to primary category
            if not parent:
                primary_category = None
                for cat, info in self.entity_context['offensive_content_category'].items():
                    if info.get('is_primary'):
                        primary_category = cat
                        break
                
                if primary_category:
                    parent = primary_category
                    extraction_result['offensive_content_category'] = {'name': parent}
                    print(f"Page {page_num}: Setting primary category '{parent}' for orphaned subcategory '{subcategory}'")
            
            if subcategory:
                self.entity_context['sub_category'][subcategory] = {
                    'parent_category': parent,
                    'last_seen': time.time(),
                    'page': page_num
                }
                print(f"Page {page_num}: Discovered subcategory '{subcategory}' under '{parent}'")
        
        if 'guideline' in extraction_result:
            guideline = extraction_result['guideline'].get('description')
            subcategory = extraction_result.get('sub_category', {}).get('name')
            if guideline:
                self.entity_context['guideline'][guideline] = {
                    'parent_subcategory': subcategory,
                    'last_seen': time.time(),
                    'page': page_num
                }
                print(f"Page {page_num}: Discovered guideline under '{subcategory}'")
        
        # Process any rules in this extraction
        if 'rules' in extraction_result:
            for rule in extraction_result['rules']:
                rule_type = rule.get('type')
                rule_desc = rule.get('description')
                
                # If guideline exists, rules are properly attached
                if 'guideline' in extraction_result:
                    # Already has proper parent
                    pass
                else:
                    # Store rule for later attachment
                    guideline_hint = rule.get('guideline_hint')
                    if guideline_hint:
                        self.entity_context['pending_rules'].append({
                            'rule': rule,
                            'page': page_num,
                            'subcategory_hint': extraction_result.get('sub_category', {}).get('name'),
                            'guideline_hint': guideline_hint
                        })
                        print(f"Page {page_num}: Stored {rule_type} '{rule_desc}' for later attachment")
        
        # Try to attach any pending rules if they match newly discovered parents
        self.try_attach_pending_rules()
        
        # Try to infer missing parent entities for this extraction
        enriched_result = self.infer_parent_entities(extraction_result)
        
        # Save updated context
        self.save_context()
        
        return enriched_result
    
    def infer_parent_entities(self, extraction_result):
        """
        Infer missing parent entities based on context from previous pages.
        """
        # Make a copy to avoid modifying the original
        enriched_result = extraction_result.copy()
        
        # If sub_category exists but offensive_content_category is missing, try to infer
        if 'sub_category' in enriched_result and 'name' in enriched_result['sub_category'] and 'offensive_content_category' not in enriched_result:
            subcategory = enriched_result['sub_category']['name']
            if subcategory in self.entity_context['sub_category']:
                parent_category = self.entity_context['sub_category'][subcategory].get('parent_category')
                if parent_category:
                    enriched_result['offensive_content_category'] = {'name': parent_category}
                    print(f"Inferred parent category '{parent_category}' for subcategory '{subcategory}'")
        
        # If guideline exists but sub_category is missing, try to infer
        if 'guideline' in enriched_result and 'description' in enriched_result['guideline'] and 'sub_category' not in enriched_result:
            guideline = enriched_result['guideline']['description']
            if guideline in self.entity_context['guideline']:
                parent_subcategory = self.entity_context['guideline'][guideline].get('parent_subcategory')
                if parent_subcategory:
                    enriched_result['sub_category'] = {'name': parent_subcategory}
                    print(f"Inferred parent subcategory '{parent_subcategory}' for guideline '{guideline}'")
                    
                    # Also check if we need to infer the category
                    if 'offensive_content_category' not in enriched_result and parent_subcategory in self.entity_context['sub_category']:
                        grandparent_category = self.entity_context['sub_category'][parent_subcategory].get('parent_category')
                        if grandparent_category:
                            enriched_result['offensive_content_category'] = {'name': grandparent_category}
                            print(f"Inferred grandparent category '{grandparent_category}' for guideline '{guideline}'")
        
        return enriched_result
    
    def try_attach_pending_rules(self):
        """
        Try to attach pending rules to their parent entities based on context.
        """
        still_pending = []
        for pending in self.entity_context['pending_rules']:
            guideline_hint = pending.get('guideline_hint')
            subcategory_hint = pending.get('subcategory_hint')
            rule = pending.get('rule')
            page = pending.get('page')
            
            if guideline_hint and guideline_hint in self.entity_context['guideline']:
                # We found the parent guideline for this rule
                parent_subcategory = self.entity_context['guideline'][guideline_hint].get('parent_subcategory')
                print(f"Attached pending rule from page {page} to guideline '{guideline_hint}' under subcategory '{parent_subcategory}'")
                # Implementation would generate a Cypher query to create this relationship
                # but we're just tracking context for now
            elif subcategory_hint and subcategory_hint in self.entity_context['sub_category']:
                # We found the parent subcategory but not the specific guideline
                parent_category = self.entity_context['sub_category'][subcategory_hint].get('parent_category')
                print(f"Partially attached pending rule from page {page} to subcategory '{subcategory_hint}' under category '{parent_category}'")
                # Could create a default guideline in this case
            else:
                # Keep this rule pending
                still_pending.append(pending)
        
        self.entity_context['pending_rules'] = still_pending
    
    def generate_cypher_for_orphaned_rules(self):
        """
        Generate Cypher queries to attach orphaned rules based on best available context.
        """
        # Implementation would generate Cypher queries for any remaining pending rules
        # using the best available context information
        pass
    
    def get_context(self):
        """Return the full entity context dictionary."""
        return self.entity_context