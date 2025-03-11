import os
import json
import time

class ContextAgent:
    """
    Agent 3: Context Integration
    
    Manages the hierarchical relationships between entities across document pages.
    Maintains a global context that gets updated as each page is processed.
    """
    
    def __init__(self, context_file="compliance_context.json"):
        """Initialize the context agent with a file path for persistent storage."""
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
    
    def process_extracted_data(self, page_num, extracted_data):
        """
        Process extracted data, update context, and handle entity relationships.
        
        Args:
            page_num: The page number being processed
            extracted_data: The structured data from Entity Extractor
            
        Returns:
            Updated entity context
        """
        # Process the offensive content category
        category_name = extracted_data.get("offensive_content_category", "Firearms & Accessories")
        
        # Handle category normalization
        if category_name:
            # Check if this is the first category we've seen
            if not self.entity_context['offensive_content_category']:
                # This is the first category - use it as the primary category
                self.entity_context['offensive_content_category'][category_name] = {
                    'last_seen': time.time(),
                    'page': page_num,
                    'is_primary': True
                }
                print(f"Page {page_num}: Set primary category '{category_name}'")
            else:
                # We already have at least one category
                # Check if this is a variant of an existing category
                primary_category = None
                for existing_cat, info in self.entity_context['offensive_content_category'].items():
                    if info.get('is_primary'):
                        primary_category = existing_cat
                        break
                
                if primary_category and category_name != primary_category:
                    # Similar category detected - normalize to primary
                    print(f"Page {page_num}: Normalizing category '{category_name}' to primary '{primary_category}'")
                    category_name = primary_category
                    
                    # Add this as an alias for the primary category
                    if 'aliases' not in self.entity_context['offensive_content_category'][primary_category]:
                        self.entity_context['offensive_content_category'][primary_category]['aliases'] = []
                    
                    if category_name not in self.entity_context['offensive_content_category'][primary_category]['aliases']:
                        self.entity_context['offensive_content_category'][primary_category]['aliases'].append(category_name)
                
                # Update timestamp for this category
                self.entity_context['offensive_content_category'][category_name] = {
                    'last_seen': time.time(),
                    'page': page_num,
                    'is_primary': category_name == primary_category
                }
        
        # Process subcategories
        subcategories = extracted_data.get("sub_categories", [])
        for subcategory in subcategories:
            if isinstance(subcategory, dict) and "name" in subcategory:
                subcategory = subcategory["name"]
            
            if subcategory:
                self.entity_context['sub_category'][subcategory] = {
                    'parent_category': category_name,
                    'last_seen': time.time(),
                    'page': page_num
                }
                print(f"Page {page_num}: Discovered subcategory '{subcategory}' under '{category_name}'")
        
        # Process guidelines
        guidelines = extracted_data.get("guidelines", [])
        for guideline in guidelines:
            if isinstance(guideline, dict) and "description" in guideline:
                guideline_desc = guideline["description"]
            else:
                guideline_desc = guideline
            
            # Determine parent subcategory
            parent_subcategory = None
            if len(subcategories) == 1:
                # If there's only one subcategory on the page, use it as parent
                if isinstance(subcategories[0], dict):
                    parent_subcategory = subcategories[0].get("name")
                else:
                    parent_subcategory = subcategories[0]
            
            if guideline_desc:
                self.entity_context['guideline'][guideline_desc] = {
                    'parent_subcategory': parent_subcategory,
                    'last_seen': time.time(),
                    'page': page_num
                }
                print(f"Page {page_num}: Discovered guideline under subcategory '{parent_subcategory}'")
        
        # Process rules
        rules = extracted_data.get("rules", [])
        for rule in rules:
            rule_type = rule.get("type")
            rule_desc = rule.get("description")
            
            # If guideline exists, rules are properly attached
            if guidelines:
                # Rules are attached to the current guideline
                pass
            else:
                # Store rule for later attachment
                guideline_hint = rule.get("guideline_hint")
                if guideline_hint:
                    self.entity_context['pending_rules'].append({
                        'rule': rule,
                        'page': page_num,
                        'subcategory_hint': subcategories[0] if subcategories else None,
                        'guideline_hint': guideline_hint
                    })
                    print(f"Page {page_num}: Stored {rule_type} '{rule_desc}' for later attachment")
        
        # Try to attach any pending rules if they match newly discovered parents
        self.try_attach_pending_rules()
        
        # Save updated context
        self.save_context()
        
        return self.entity_context
    
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
    
    def finalize_context(self):
        """
        Finalize context after all pages are processed.
        Attach orphaned rules, perform cleanup, etc.
        """
        # Attach any pending rules that are still orphaned
        self.try_attach_pending_rules()
        
        # Additional integrity checks or cleanup can go here
        
        # Save final context
        self.save_context()
        
        return self.entity_context