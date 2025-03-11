import json
import re

class CypherGeneratorAgent:
    """
    Agent 4: Cypher Query Generation
    
    Generates Neo4j Cypher queries from the consolidated entity context.
    Can generate incremental queries per page or a final comprehensive query.
    """
    
    def __init__(self):
        pass
    
    def build_cypher(self, context):
        """
        Generate Cypher queries from the consolidated context object.
        
        Args:
            context: The full entity context from ContextAgent
            
        Returns:
            A JSON object with a "cypher_query" field containing the Neo4j query.
        """
        cypher_parts = []
        
        # Find the primary category
        primary_category = None
        for cat_name, cat_info in context["offensive_content_category"].items():
            if cat_info.get('is_primary'):
                primary_category = cat_name
                break
        
        # Default if no primary category found
        if not primary_category and context["offensive_content_category"]:
            # Just use the first category
            primary_category = list(context["offensive_content_category"].keys())[0]
        elif not primary_category:
            primary_category = "Firearms & Accessories"
        
        # 1. Create the primary offensive content category
        cypher_parts.append(f"MERGE (occ:Offensive_Content_Category {{name: '{self._escape_quotes(primary_category)}'}})")
        
        # 2. Add all subcategories
        for idx, (subcat_name, subcat_info) in enumerate(context["sub_category"].items(), 1):
            parent_category = subcat_info.get("parent_category", primary_category)
            
            # Sanitize parent category to match primary if needed
            if parent_category != primary_category:
                for cat_name, cat_info in context["offensive_content_category"].items():
                    if cat_info.get('is_primary') and cat_name == primary_category:
                        # Check if this parent is an alias
                        aliases = cat_info.get('aliases', [])
                        if parent_category in aliases:
                            parent_category = primary_category
                            break
            
            subcat_name_escaped = self._escape_quotes(subcat_name)
            cypher_parts.append(f"MERGE (sc{idx}:Sub_Category {{name: '{subcat_name_escaped}'}})")
            
            # Only connect to primary category if parent matches or is normalized
            if parent_category == primary_category:
                cypher_parts.append(f"MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc{idx})")
        
        # 3. Add all guidelines with connections to subcategories
        for g_idx, (guideline_desc, guideline_info) in enumerate(context["guideline"].items(), 1):
            parent_subcategory = guideline_info.get("parent_subcategory")
            
            guideline_desc_escaped = self._escape_quotes(guideline_desc)
            cypher_parts.append(f"MERGE (g{g_idx}:Guideline {{description: '{guideline_desc_escaped}'}})")
            
            # Connect to parent subcategory if available
            if parent_subcategory:
                # Find the subcategory index
                for sc_idx, (subcat_name, _) in enumerate(context["sub_category"].items(), 1):
                    if subcat_name == parent_subcategory:
                        cypher_parts.append(f"MERGE (sc{sc_idx})-[:HAS_GUIDELINE]->(g{g_idx})")
                        break
        
        # 4. Process pending rules
        rule_counter = {
            "imperium_rule": 1,
            "policy_rule": 1,
            "image_detection_rule": 1
        }
        
        # Function to add a rule with the appropriate type
        def add_rule_to_cypher(rule, guideline_idx=None):
            rule_type = rule.get("type", "policy_rule").lower()
            rule_desc = rule.get("description", "")
            rule_status = rule.get("status", "PROHIBITS")
            rule_id = rule.get("rule_id", "")
            
            rule_desc_escaped = self._escape_quotes(rule_desc)
            
            if rule_type == "imperium_rule":
                node_idx = rule_counter["imperium_rule"]
                cypher_parts.append(f"MERGE (ir{node_idx}:Imperium_Rule {{description: '{rule_desc_escaped}'{', rule_id: \'' + rule_id + '\'' if rule_id else ''}}})")
                if guideline_idx:
                    cypher_parts.append(f"MERGE (g{guideline_idx})-[rImp:{rule_status}]->(ir{node_idx})")
                rule_counter["imperium_rule"] += 1
            
            elif rule_type == "policy_rule":
                node_idx = rule_counter["policy_rule"]
                cypher_parts.append(f"MERGE (pr{node_idx}:Policy_Rule {{description: '{rule_desc_escaped}'}})")
                if guideline_idx:
                    cypher_parts.append(f"MERGE (g{guideline_idx})-[rPol:{rule_status}]->(pr{node_idx})")
                rule_counter["policy_rule"] += 1
            
            elif rule_type == "image_detection_rule":
                node_idx = rule_counter["image_detection_rule"]
                cypher_parts.append(f"MERGE (idr{node_idx}:Image_Detection_Rule {{description: '{rule_desc_escaped}'}})")
                if guideline_idx:
                    cypher_parts.append(f"MERGE (g{guideline_idx})-[rImg:{rule_status}]->(idr{node_idx})")
                rule_counter["image_detection_rule"] += 1
        
        # Process pending rules
        for pending in context["pending_rules"]:
            rule = pending.get("rule")
            guideline_hint = pending.get("guideline_hint")
            
            if rule and guideline_hint:
                # Find the guideline index
                for g_idx, (guideline_desc, _) in enumerate(context["guideline"].items(), 1):
                    if guideline_desc == guideline_hint:
                        add_rule_to_cypher(rule, g_idx)
                        break
                else:
                    # If guideline not found, just add the rule without connection
                    add_rule_to_cypher(rule)
            elif rule:
                add_rule_to_cypher(rule)
        
        # Join all Cypher parts
        cypher_query = " ".join(cypher_parts)
        
        # Return properly formatted JSON
        return {"cypher_query": cypher_query}
    
    def build_incremental_cypher(self, context, page_data, page_num):
        """
        Generate an incremental Cypher query for a single page's data.
        
        Args:
            context: The full entity context
            page_data: The extracted data from this specific page
            page_num: The page number
            
        Returns:
            A JSON object with a "cypher_query" field for this page's entities.
        """
        cypher_parts = []
        
        # Find the primary category from context
        primary_category = None
        for cat_name, cat_info in context["offensive_content_category"].items():
            if cat_info.get('is_primary'):
                primary_category = cat_name
                break
        
        # Default if no primary category found
        if not primary_category:
            primary_category = "Firearms & Accessories"
        
        # Get entities from this page
        category_name = page_data.get("offensive_content_category", primary_category)
        subcategories = page_data.get("sub_categories", [])
        guidelines = page_data.get("guidelines", [])
        rules = page_data.get("rules", [])
        
        # Normalize category if needed
        if category_name != primary_category:
            for cat_name, cat_info in context["offensive_content_category"].items():
                if cat_info.get('is_primary') and cat_name == primary_category:
                    # Check if this category is an alias
                    aliases = cat_info.get('aliases', [])
                    if category_name in aliases:
                        category_name = primary_category
                        break
        
        # 1. Add the offensive content category (normalized to primary)
        cypher_parts.append(f"MERGE (occ:Offensive_Content_Category {{name: '{self._escape_quotes(primary_category)}'}})")
        
        # 2. Add subcategories
        for idx, subcategory in enumerate(subcategories, 1):
            if isinstance(subcategory, dict) and "name" in subcategory:
                subcategory = subcategory["name"]
            
            subcat_name_escaped = self._escape_quotes(subcategory)
            cypher_parts.append(f"MERGE (sc{idx}:Sub_Category {{name: '{subcat_name_escaped}'}})")
            cypher_parts.append(f"MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc{idx})")
        
        # 3. Add guidelines with connections to subcategories
        for g_idx, guideline in enumerate(guidelines, 1):
            if isinstance(guideline, dict) and "description" in guideline:
                guideline_desc = guideline["description"]
            else:
                guideline_desc = guideline
            
            guideline_desc_escaped = self._escape_quotes(guideline_desc)
            cypher_parts.append(f"MERGE (g{g_idx}:Guideline {{description: '{guideline_desc_escaped}'}})")
            
            # Connect to parent subcategory
            # If we have just one subcategory, connect the guideline to it
            if len(subcategories) == 1:
                cypher_parts.append(f"MERGE (sc1)-[:HAS_GUIDELINE]->(g{g_idx})")
        
        # 4. Add rules with connections to guidelines
        rule_counter = {
            "imperium_rule": 1,
            "policy_rule": 1, 
            "image_detection_rule": 1
        }
        
        for rule in rules:
            rule_type = rule.get("type", "policy_rule").lower()
            rule_desc = rule.get("description", "")
            rule_status = rule.get("status", "PROHIBITS")
            rule_id = rule.get("rule_id", "")
            
            rule_desc_escaped = self._escape_quotes(rule_desc)
            
            if rule_type == "imperium_rule":
                node_idx = rule_counter["imperium_rule"]
                cypher_parts.append(f"MERGE (ir{node_idx}:Imperium_Rule {{description: '{rule_desc_escaped}'{', rule_id: \'' + rule_id + '\'' if rule_id else ''}}})")
                # Connect to guideline if available
                if guidelines:
                    cypher_parts.append(f"MERGE (g1)-[rImp:{rule_status}]->(ir{node_idx})")
                rule_counter["imperium_rule"] += 1
            
            elif rule_type == "policy_rule":
                node_idx = rule_counter["policy_rule"]
                cypher_parts.append(f"MERGE (pr{node_idx}:Policy_Rule {{description: '{rule_desc_escaped}'}})")
                # Connect to guideline if available
                if guidelines:
                    cypher_parts.append(f"MERGE (g1)-[rPol:{rule_status}]->(pr{node_idx})")
                rule_counter["policy_rule"] += 1
            
            elif rule_type == "image_detection_rule":
                node_idx = rule_counter["image_detection_rule"]
                cypher_parts.append(f"MERGE (idr{node_idx}:Image_Detection_Rule {{description: '{rule_desc_escaped}'}})")
                # Connect to guideline if available
                if guidelines:
                    cypher_parts.append(f"MERGE (g1)-[rImg:{rule_status}]->(idr{node_idx})")
                rule_counter["image_detection_rule"] += 1
        
        # Join all Cypher parts
        cypher_query = " ".join(cypher_parts)
        
        # Return properly formatted JSON with page info
        return {
            "cypher_query": cypher_query,
            "page": page_num
        }
    
    def _escape_quotes(self, text):
        """Escape single quotes in text for Cypher queries."""
        if not text:
            return ""
        return str(text).replace("'", "\\'").replace('"', '\\"')