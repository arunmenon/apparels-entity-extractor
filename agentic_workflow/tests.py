import os
import sys
import unittest
import json
from unittest.mock import patch, Mock

# Add the parent directory to the path so we can import the agentic_workflow module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentic_workflow import PageClassifierAgent, EntityExtractorAgent, ContextAgent, CypherGeneratorAgent

class AgenticWorkflowTests(unittest.TestCase):
    """Test cases for the agentic workflow components."""
    
    def test_page_classifier(self):
        """Test the PageClassifierAgent with a mock response."""
        with patch('requests.post') as mock_post:
            # Set up the mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "FULL_TOC"
                        }
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Create the classifier and call classify_page
            classifier = PageClassifierAgent(api_key="fake_key", model="gpt-4")
            result = classifier.classify_page("fake_base64_image")
            
            # Assert that the result is as expected
            self.assertEqual(result, "FULL_TOC")
            
            # Verify that requests.post was called once
            mock_post.assert_called_once()
    
    def test_entity_extractor_toc(self):
        """Test the EntityExtractorAgent with a mock TOC response."""
        with patch('requests.post') as mock_post:
            # Set up the mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": """{"cypher_query": "MERGE (occ:Offensive_Content_Category {name: 'Firearms & Accessories'}) MERGE (sc1:Sub_Category {name: 'Ammunition'}) MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc1)"}"""
                        }
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Create the extractor and call extract_entities
            extractor = EntityExtractorAgent(
                api_key="fake_key",
                model="gpt-4",
                toc_prompt_system="System prompt",
                toc_prompt_user="User prompt",
                std_prompt_system="System prompt",
                std_prompt_user="User prompt"
            )
            result = extractor.extract_entities("FULL_TOC", "fake_base64_image")
            
            # Assert that the result contains the expected data
            self.assertEqual(result["offensive_content_category"], "Firearms & Accessories")
            self.assertEqual(result["sub_categories"], ["Ammunition"])
            
            # Verify that requests.post was called once
            mock_post.assert_called_once()
    
    def test_context_agent(self):
        """Test the ContextAgent with simple data."""
        # Create a temporary context file
        context_file = "test_context.json"
        
        # Create the context agent
        context_agent = ContextAgent(context_file=context_file)
        
        # Define test data
        test_data = {
            "offensive_content_category": "Firearms & Accessories",
            "sub_categories": ["Ammunition", "Firearms"],
            "guidelines": [{"description": "Test guideline"}],
            "rules": [
                {
                    "type": "policy_rule",
                    "description": "Test rule",
                    "status": "PROHIBITS"
                }
            ]
        }
        
        # Process the test data
        updated_context = context_agent.process_extracted_data(1, test_data)
        
        # Verify the context was updated
        self.assertIn("Firearms & Accessories", updated_context["offensive_content_category"])
        self.assertIn("Ammunition", updated_context["sub_category"])
        self.assertIn("Test guideline", updated_context["guideline"])
        
        # Clean up
        if os.path.exists(context_file):
            os.remove(context_file)
    
    def test_cypher_generator(self):
        """Test the CypherGeneratorAgent."""
        # Create a test context
        test_context = {
            "offensive_content_category": {
                "Firearms & Accessories": {
                    "is_primary": True,
                    "last_seen": 12345,
                    "page": 1
                }
            },
            "sub_category": {
                "Ammunition": {
                    "parent_category": "Firearms & Accessories",
                    "last_seen": 12345,
                    "page": 1
                },
                "Firearms": {
                    "parent_category": "Firearms & Accessories",
                    "last_seen": 12345,
                    "page": 1
                }
            },
            "guideline": {
                "Test guideline": {
                    "parent_subcategory": "Ammunition",
                    "last_seen": 12345,
                    "page": 1
                }
            },
            "pending_rules": []
        }
        
        # Create the cypher generator
        cypher_generator = CypherGeneratorAgent()
        
        # Generate the cypher query
        result = cypher_generator.build_cypher(test_context)
        
        # Verify the result contains a cypher_query field
        self.assertIn("cypher_query", result)
        
        # Verify the cypher query contains the expected entities
        self.assertIn("Firearms & Accessories", result["cypher_query"])
        self.assertIn("Ammunition", result["cypher_query"])
        self.assertIn("Firearms", result["cypher_query"])
        self.assertIn("Test guideline", result["cypher_query"])

if __name__ == "__main__":
    unittest.main()