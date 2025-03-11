import requests
import json
import re
import time

class EntityExtractorAgent:
    """
    Agent 2: Entity Extraction Agent
    
    Extracts structured data from document pages based on the page classification.
    Uses different prompts for TOC vs regular pages.
    """
    
    def __init__(self, api_key, model, toc_prompt_system, toc_prompt_user, std_prompt_system, std_prompt_user):
        self.api_key = api_key
        self.model = model
        self.toc_prompt_system = toc_prompt_system
        self.toc_prompt_user = toc_prompt_user
        self.std_prompt_system = std_prompt_system
        self.std_prompt_user = std_prompt_user
        
        # Compile regex patterns for extraction help
        self.category_pattern = re.compile(r'MERGE\s+\((?:occ|c):Offensive_Content_Category\s+\{name:\s*\'([^\']+)\'\}\)')
        self.subcategory_pattern = re.compile(r'MERGE\s+\((?:sc\d+|s\d+):Sub_Category\s+\{name:\s*\'([^\']+)\'\}\)')

    def extract_entities(self, classification, base64_image):
        """
        Returns a structured JSON dict describing the recognized entities/hierarchy.
        """
        # Select the appropriate system and user prompts based on page type
        if classification in ["FULL_TOC", "HYBRID"]:
            system_prompt = self.toc_prompt_system
            user_prompt = self.toc_prompt_user
            max_tokens = 1024
        else:
            system_prompt = self.std_prompt_system
            user_prompt = self.std_prompt_user
            max_tokens = 3072

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": { "url": f"data:image/png;base64,{base64_image}" }
                        }
                    ]
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0
        }
        
        # Initialize retries
        retries = 0
        max_retries = 3
        backoff = 2  # seconds

        while retries < max_retries:
            try:
                response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                structured_text = result["choices"][0]["message"]["content"].strip()
                
                # Parse the response differently based on page classification
                if classification in ["FULL_TOC", "HYBRID"]:
                    return self._process_toc_response(structured_text)
                else:
                    return self._process_regular_response(structured_text)
                    
            except Exception as e:
                print(f"Error during entity extraction: {str(e)}")
                retries += 1
                if retries < max_retries:
                    print(f"Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff
                else:
                    # Fallback with minimal data
                    return {
                        "offensive_content_category": "Firearms & Accessories",
                        "error": str(e),
                        "sub_categories": [],
                        "guidelines": [],
                        "rules": []
                    }
    
    def _extract_subcategories_from_text(self, text):
        """Extract subcategories from text using various regex patterns"""
        subcats = []
        
        # Try a series of patterns, from specific to general
        patterns = [
            r"MERGE \(sc\d+:Sub_Category \{name: '([^']+)'\}\)",  # Standard pattern
            r"MERGE \(s\d+:Sub_Category \{name: '([^']+)'\}\)",   # Alternative naming
            r"Sub_Category\s*\{name:\s*'([^']+)'\}",              # More flexible
            r"{name:\s*'([^']+)'}"                                # Most general
        ]
        
        # Try each pattern
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                for match in matches:
                    if match and match not in subcats:
                        subcats.append(match)
        
        # If we found subcategories, return them
        if subcats:
            return subcats
        
        # Last resort: Look for anything in quotes that might be a subcategory
        potential_subcats = re.findall(r"'([^']+)'", text)
        return [s for s in potential_subcats if len(s) > 3 and s not in subcats]  # Filter out short strings
    
    def _process_toc_response(self, structured_text):
        """Process and structure the TOC extraction response"""
        # Try to parse as JSON first
        try:
            data = json.loads(structured_text)
            if "cypher_query" in data:
                # Extract data from Cypher query
                cypher_query = data["cypher_query"]
                
                # Extract category name
                category_match = self.category_pattern.search(cypher_query)
                category_name = category_match.group(1) if category_match else "Firearms & Accessories"
                
                # Extract subcategories
                subcategories = self._extract_subcategories_from_text(cypher_query)
                
                # Return structured data
                return {
                    "offensive_content_category": category_name,
                    "sub_categories": subcategories,
                    "guidelines": [],
                    "rules": []
                }
        except json.JSONDecodeError:
            pass
        
        # If JSON parsing failed, extract data directly from text
        subcategories = self._extract_subcategories_from_text(structured_text)
        
        # Extract category if possible
        category_match = self.category_pattern.search(structured_text)
        category_name = category_match.group(1) if category_match else "Firearms & Accessories"
        
        # Return structured format
        return {
            "offensive_content_category": category_name,
            "sub_categories": subcategories,
            "guidelines": [],
            "rules": []
        }
    
    def _process_regular_response(self, structured_text):
        """Process and structure the standard page extraction response"""
        # Try parsing as JSON
        try:
            # Handle code blocks
            if "```json" in structured_text:
                json_block_start = structured_text.find('```json')
                json_block_end = structured_text.find('```', json_block_start + 7)
                
                if json_block_start != -1 and json_block_end != -1:
                    json_content = structured_text[json_block_start + 7:json_block_end].strip()
                    structured_text = json_content
            
            # Clean up newlines and control characters
            structured_text = re.sub(r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', structured_text)
            
            # Handle special case with "cypher_query" field but still try to extract structured data
            if '"cypher_query":' in structured_text:
                try:
                    data = json.loads(structured_text)
                    
                    cypher_query = data.get("cypher_query", "")
                    
                    # Extract category
                    category_match = self.category_pattern.search(cypher_query)
                    category_name = category_match.group(1) if category_match else "Firearms & Accessories"
                    
                    # Extract subcategories
                    subcategories = self._extract_subcategories_from_text(cypher_query)
                    
                    # Extract guidelines (simple approach)
                    guidelines = []
                    guideline_pattern = r"MERGE \(g\d+:Guideline \{description: '([^']+)'\}\)"
                    guideline_matches = re.findall(guideline_pattern, cypher_query)
                    if guideline_matches:
                        guidelines = guideline_matches
                    
                    # Extract rules (simple approach)
                    rules = []
                    rule_patterns = [
                        r"MERGE \(ir\d+:Imperium_Rule \{description: '([^']+)'(?:, rule_id: '([^']+)')?\}\)",
                        r"MERGE \(pr\d+:Policy_Rule \{description: '([^']+)'\}\)",
                        r"MERGE \(idr\d+:Image_Detection_Rule \{description: '([^']+)'\}\)"
                    ]
                    
                    for pattern in rule_patterns:
                        rule_matches = re.findall(pattern, cypher_query)
                        if rule_matches:
                            for match in rule_matches:
                                rule_desc = match[0] if isinstance(match, tuple) else match
                                rule_id = match[1] if isinstance(match, tuple) and len(match) > 1 else None
                                
                                rule_type = "unknown"
                                if "Imperium_Rule" in pattern:
                                    rule_type = "imperium_rule"
                                elif "Policy_Rule" in pattern:
                                    rule_type = "policy_rule"
                                elif "Image_Detection_Rule" in pattern:
                                    rule_type = "image_detection_rule"
                                
                                # Extract rule status
                                status = "PROHIBITS"  # Default
                                if "-[r" in cypher_query and "ALLOWS" in cypher_query:
                                    status = "ALLOWS"
                                
                                rule = {
                                    "type": rule_type,
                                    "description": rule_desc,
                                    "status": status
                                }
                                
                                if rule_id:
                                    rule["rule_id"] = rule_id
                                    
                                rules.append(rule)
                    
                    # Return the structured data
                    return {
                        "offensive_content_category": category_name,
                        "sub_categories": subcategories,
                        "guidelines": [{"description": g} for g in guidelines],
                        "rules": rules
                    }
                    
                except json.JSONDecodeError:
                    # If we couldn't parse the JSON but have a cypher_query
                    # Try to extract structured data from the cypher query string
                    pass
            
            # If we're here, try to parse as regular JSON
            data = json.loads(structured_text)
            
            # Extract and restructure the data
            result = {}
            
            # Handle different possible JSON structures
            if "offensive_content_category" in data:
                if isinstance(data["offensive_content_category"], dict):
                    result["offensive_content_category"] = data["offensive_content_category"].get("name", "Firearms & Accessories")
                else:
                    result["offensive_content_category"] = data["offensive_content_category"]
            else:
                result["offensive_content_category"] = "Firearms & Accessories"
                
            # Handle subcategories
            if "sub_categories" in data:
                result["sub_categories"] = data["sub_categories"]
            elif "sub_category" in data:
                if isinstance(data["sub_category"], dict):
                    result["sub_categories"] = [data["sub_category"].get("name")]
                elif isinstance(data["sub_category"], list):
                    result["sub_categories"] = [sc.get("name") if isinstance(sc, dict) else sc for sc in data["sub_category"]]
                else:
                    result["sub_categories"] = [data["sub_category"]]
            else:
                result["sub_categories"] = []
                
            # Handle guidelines
            if "guidelines" in data:
                result["guidelines"] = data["guidelines"]
            elif "guideline" in data:
                if isinstance(data["guideline"], dict):
                    result["guidelines"] = [data["guideline"]]
                elif isinstance(data["guideline"], list):
                    result["guidelines"] = data["guideline"]
                else:
                    result["guidelines"] = [{"description": data["guideline"]}]
            else:
                result["guidelines"] = []
                
            # Handle rules
            if "rules" in data:
                result["rules"] = data["rules"]
            elif "rule" in data:
                if isinstance(data["rule"], dict):
                    result["rules"] = [data["rule"]]
                elif isinstance(data["rule"], list):
                    result["rules"] = data["rule"]
                else:
                    result["rules"] = []
            else:
                result["rules"] = []
                
            return result
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error parsing extraction response: {str(e)}")
            # Create a minimal response
            return {
                "offensive_content_category": "Firearms & Accessories",
                "sub_categories": [],
                "guidelines": [],
                "rules": [],
                "raw_response": structured_text[:500] + ("..." if len(structured_text) > 500 else "")
            }