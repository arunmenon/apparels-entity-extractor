import requests
import json
import time
import sys
import os

class PageClassifierAgent:
    """
    Agent 1: Page Classification Agent
    
    Classifies pages as FULL_TOC, HYBRID, or REGULAR based on content analysis.
    """
    
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def classify_page(self, base64_image):
        """
        Returns one of: 'FULL_TOC', 'HYBRID', or 'REGULAR'.
        """
        toc_detection_prompt = """
        You are a document classifier that identifies Table of Contents pages.
        A true Table of Contents page must contain a clear "Table of Contents" heading or title
        followed by bulleted or numbered lists of subcategories.

        Return EXACTLY ONE of these options:
        - FULL_TOC
        - HYBRID
        - REGULAR
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": toc_detection_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Is this a Table of Contents page? 
                                       Only classify as TOC if there's an explicit "Table of Contents" heading 
                                       with visible bullet points. 
                                       Respond with ONLY "FULL_TOC", "HYBRID", or "REGULAR"."""
                        },
                        {
                            "type": "image_url",
                            "image_url": { "url": f"data:image/png;base64,{base64_image}" }
                        }
                    ]
                }
            ],
            "max_tokens": 50,
            "temperature": 0
        }

        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip().upper()
            
            # Validate response
            if "FULL_TOC" in content:
                return "FULL_TOC"
            elif "HYBRID" in content:
                return "HYBRID"
            else:
                return "REGULAR"
                
        except Exception as e:
            print(f"Error during page classification: {str(e)}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    print(f"API error details: {error_detail}")
                except:
                    print(f"Response status code: {e.response.status_code}")
                    print(f"Response text: {e.response.text}")
            # Fallback in case of error
            return "REGULAR"