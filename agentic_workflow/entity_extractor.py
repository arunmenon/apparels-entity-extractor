import requests
import json
import re
import time
import logging
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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

    def extract_entities(self, classification, base64_image, context=None):
        """
        Returns a structured JSON dict describing the recognized entities/hierarchy.
        Context parameter can be provided to enable context-aware extraction.
        """
        print("\n=== ENTITY EXTRACTION TRACING ===")
        start_time = time.time()
        print(f"Starting extraction for {classification} page")
        
        # Select the appropriate system and user prompts based on page type
        if classification in ["FULL_TOC", "HYBRID"]:
            system_prompt = self.toc_prompt_system
            user_prompt = self.toc_prompt_user
            max_tokens = 2048  # Reduced from 4096 to improve performance
            print(f"Using TOC prompts with max_tokens={max_tokens}")
        else:
            system_prompt = self.std_prompt_system
            user_prompt = self.std_prompt_user
            max_tokens = 2048  # Reduced from 3072 to improve performance
            print(f"Using standard prompts with max_tokens={max_tokens}")
            
        # Enhance prompts with context if available
        if context and classification not in ["FULL_TOC", "HYBRID"]:
            # Don't apply context to TOC pages as they define the primary structure
            from .enhanced_extractor import create_context_aware_prompt
            system_prompt, user_prompt = create_context_aware_prompt(
                system_prompt, user_prompt, context
            )
            print("Enhanced extraction with context from previous pages")

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
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "timeout": 60  # Add timeout parameter to prevent hanging
        }
        
        # Initialize retries
        retries = 0
        max_retries = 3
        backoff = 2  # seconds

        while retries < max_retries:
            try:
                print(f"\n[API Call] Sending request to OpenAI API at {time.strftime('%H:%M:%S')}")
                api_start_time = time.time()
                
                # Use OpenAI client instead of requests for better logging
                client = OpenAI(api_key=self.api_key)
                
                # Log request details
                logger = logging.getLogger("extraction")
                logger.info(f"API Request: model={self.model}, max_tokens={max_tokens}, temperature=0.0")
                
                completion = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]}
                    ],
                    max_tokens=max_tokens,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    timeout=120  # 2 minute timeout
                )
                
                # Log response details
                logger.info(f"API Response: finish_reason={completion.choices[0].finish_reason}, " +
                           f"tokens={completion.usage.total_tokens}")
                
                # Create a response-like object for backward compatibility
                class MockResponse:
                    def __init__(self, status_code):
                        self.status_code = status_code
                    
                    def raise_for_status(self):
                        pass
                    
                    def json(self):
                        return {
                            "choices": [{"message": {"content": completion.choices[0].message.content}}],
                            "usage": {
                                "prompt_tokens": completion.usage.prompt_tokens,
                                "completion_tokens": completion.usage.completion_tokens,
                                "total_tokens": completion.usage.total_tokens
                            }
                        }
                
                response = MockResponse(200)
                
                api_duration = time.time() - api_start_time
                print(f"[API Response] Received in {api_duration:.2f} seconds with status {response.status_code}")
                
                response.raise_for_status()
                
                result = response.json()
                
                # Log token usage
                if "usage" in result:
                    usage = result["usage"]
                    print(f"[Token Usage] Prompt: {usage.get('prompt_tokens', 'N/A')}, " +
                          f"Completion: {usage.get('completion_tokens', 'N/A')}, " +
                          f"Total: {usage.get('total_tokens', 'N/A')}")
                
                structured_text = result["choices"][0]["message"]["content"].strip()
                
                # Log first 100 chars of response for debugging
                preview = structured_text[:100] + "..." if len(structured_text) > 100 else structured_text
                print(f"[Response Preview] {preview}")
                
                processing_start = time.time()
                print(f"[Processing] Starting response processing")
                
                # Parse the response differently based on page classification
                if classification in ["FULL_TOC", "HYBRID"]:
                    result = self._process_toc_response(structured_text)
                else:
                    result = self._process_regular_response(structured_text)
                
                processing_duration = time.time() - processing_start
                print(f"[Processing] Completed in {processing_duration:.2f} seconds")
                print(f"[Results] Extracted {len(result.get('sub_categories', []))} subcategories")
                
                total_duration = time.time() - start_time
                print(f"[Complete] Total extraction time: {total_duration:.2f} seconds")
                
                return result
                    
            except Exception as e:
                print(f"[ERROR] Entity extraction failed: {str(e)}")
                retries += 1
                if retries < max_retries:
                    print(f"[Retry] Attempt {retries+1}/{max_retries} in {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff
                else:
                    total_duration = time.time() - start_time
                    print(f"[FAILED] All retries failed after {total_duration:.2f} seconds")
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
    
    def _validate_subcategory(self, subcat):
        """Validate a subcategory to prevent hallucination patterns"""
        # Skip JSON keys that might have been captured
        if subcat in ["offensive_content_category", "sub_categories", "guidelines", "rules"]:
            return False
            
        # Check for nested/recursive patterns by counting colons and repeated segments
        parts = subcat.split(":")
        if len(parts) > 3:  # Too many nesting levels
            return False
            
        # Detect repetitive patterns like "X: X: X:"
        if len(parts) > 1:
            cleaned_parts = [p.strip() for p in parts]
            # Check for repeating patterns
            for i in range(len(cleaned_parts)-1):
                if cleaned_parts[i] == cleaned_parts[i+1]:
                    return False
                    
        return True
    
    def _process_toc_response(self, structured_text):
        """Process and structure the TOC extraction response"""
        # Try to parse as JSON first
        try:
            # Handle code blocks (in case the model returns markdown-formatted code blocks)
            if "```json" in structured_text:
                json_block_start = structured_text.find('```json')
                json_block_end = structured_text.find('```', json_block_start + 7)
                
                if json_block_start != -1 and json_block_end != -1:
                    json_content = structured_text[json_block_start + 7:json_block_end].strip()
                    structured_text = json_content
            
            # Try to parse JSON
            data = json.loads(structured_text)
            
            # Check if data is already in the expected format
            if "offensive_content_category" in data and "sub_categories" in data:
                # Filter subcategories to prevent hallucination
                valid_subcats = []
                seen = set()
                
                for subcat in data.get("sub_categories", []):
                    # Only add valid, non-duplicate subcategories
                    if isinstance(subcat, str) and self._validate_subcategory(subcat) and subcat not in seen:
                        seen.add(subcat)
                        valid_subcats.append(subcat)
                
                # Return filtered data
                return {
                    "offensive_content_category": data.get("offensive_content_category", "Firearms & Accessories"),
                    "sub_categories": valid_subcats,
                    "guidelines": [],
                    "rules": []
                }
            
            # For backward compatibility - handle legacy cypher query format
            if "cypher_query" in data:
                # Extract data from Cypher query
                cypher_query = data["cypher_query"]
                
                # Extract category name
                category_match = self.category_pattern.search(cypher_query)
                category_name = category_match.group(1) if category_match else "Firearms & Accessories"
                
                # Extract subcategories
                subcategories = self._extract_subcategories_from_text(cypher_query)
                
                # Filter subcategories
                valid_subcats = []
                seen = set()
                for subcat in subcategories:
                    if self._validate_subcategory(subcat) and subcat not in seen:
                        seen.add(subcat)
                        valid_subcats.append(subcat)
                
                # Return structured data
                return {
                    "offensive_content_category": category_name,
                    "sub_categories": valid_subcats,
                    "guidelines": [],
                    "rules": []
                }
                
        except json.JSONDecodeError as e:
            # If JSON parsing failed, try to extract as much as possible
            print(f"Warning: Failed to parse TOC response as JSON ({str(e)}). Attempting extraction from raw text.")
            
            # First, try to extract a JSON object if one exists in the text
            json_start = structured_text.find('{')
            json_end = structured_text.rfind('}')
            
            if json_start >= 0 and json_end > json_start:
                try:
                    potential_json = structured_text[json_start:json_end+1]
                    data = json.loads(potential_json)
                    
                    if "offensive_content_category" in data and "sub_categories" in data:
                        # Filter subcategories
                        valid_subcats = []
                        seen = set()
                        for subcat in data.get("sub_categories", []):
                            if isinstance(subcat, str) and self._validate_subcategory(subcat) and subcat not in seen:
                                seen.add(subcat)
                                valid_subcats.append(subcat)
                                
                        return {
                            "offensive_content_category": data.get("offensive_content_category", "Firearms & Accessories"),
                            "sub_categories": valid_subcats,
                            "guidelines": [],
                            "rules": []
                        }
                except:
                    pass
            
            # Look for subcategories in the raw text by finding quoted strings
            subcategories = []
            
            # Look for patterns like "subcategory"
            quoted_items = re.findall(r'"([^"]+)"', structured_text)
            subcategories.extend([item for item in quoted_items if len(item) > 3])
            
            # Look for patterns like: "sub_categories": ["item1", "item2"...]
            subcat_list_match = re.search(r'"sub_categories"\s*:\s*\[(.*?)\]', structured_text, re.DOTALL)
            if subcat_list_match:
                subcat_text = subcat_list_match.group(1)
                quoted_subcats = re.findall(r'"([^"]+)"', subcat_text)
                subcategories.extend([item for item in quoted_subcats if len(item) > 3])
            
            # Filter subcategories and remove duplicates while preserving order
            valid_subcats = []
            seen = set()
            for subcat in subcategories:
                if self._validate_subcategory(subcat) and subcat not in seen:
                    seen.add(subcat)
                    valid_subcats.append(subcat)
                    
            # If we found subcategories, use them
            if valid_subcats:
                return {
                    "offensive_content_category": "Firearms & Accessories",
                    "sub_categories": valid_subcats,
                    "guidelines": [],
                    "rules": []
                }
        
        # If all else fails, use the generic extractor
        subcategories = self._extract_subcategories_from_text(structured_text)
        
        # Try to extract any listed subcategories using a simple pattern
        if not subcategories:
            list_items = re.findall(r'(?:^|\n)\s*[•\-*]\s*(.+?)(?:$|\n)', structured_text)
            if list_items:
                subcategories = [item.strip() for item in list_items if len(item.strip()) > 3]
        
        # Filter results one last time
        valid_subcats = []
        seen = set()
        for subcat in subcategories:
            if self._validate_subcategory(subcat) and subcat not in seen:
                seen.add(subcat)
                valid_subcats.append(subcat)
        
        # Return structured format
        return {
            "offensive_content_category": "Firearms & Accessories",
            "sub_categories": valid_subcats,
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
            
            # Parse the JSON response
            data = json.loads(structured_text)
            
            # Check if data already contains the expected structure
            if "offensive_content_category" in data and "sub_categories" in data:
                # Ensure all required fields exist
                result = {
                    "offensive_content_category": data.get("offensive_content_category", "Firearms & Accessories"),
                    "sub_categories": data.get("sub_categories", []),
                    "guidelines": data.get("guidelines", []),
                    "rules": data.get("rules", [])
                }
                return result
            
            # Handle legacy format with "cypher_query" field (for backward compatibility)
            if "cypher_query" in data:
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
            
            # If we're here, the data doesn't match our expected format
            # Try to extract as much as possible from other JSON formats
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