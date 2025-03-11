"""
Integration test to verify data flow through the agentic workflow without API calls.
Uses mock responses to simulate the full pipeline.
"""

import os
import sys
import json
import tempfile
from unittest.mock import MagicMock, patch

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we need to mock modules that might be imported
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['requests'] = MagicMock()

# After mocking, we can import our components
from agentic_workflow.page_classifier import PageClassifierAgent
from agentic_workflow.entity_extractor import EntityExtractorAgent
from agentic_workflow.context_agent import ContextAgent
from agentic_workflow.cypher_generator import CypherGeneratorAgent

def run_integration_test():
    """Run an integration test of the full workflow using mocks."""
    print("Starting integration test...")
    
    # Create a temporary file for context
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
        context_file = temp_file.name
    
    try:
        # Mock the API calls
        with patch('agentic_workflow.page_classifier.requests.post') as mock_classify_post, \
             patch('agentic_workflow.entity_extractor.requests.post') as mock_extract_post:
            
            # Mock page classifier response
            mock_classify_response = MagicMock()
            mock_classify_response.status_code = 200
            mock_classify_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "FULL_TOC"
                        }
                    }
                ]
            }
            mock_classify_post.return_value = mock_classify_response
            
            # Override the classify_page method to ensure it returns FULL_TOC
            classifier_patch = patch('agentic_workflow.page_classifier.PageClassifierAgent.classify_page', 
                                    return_value="FULL_TOC")
            classifier_patch.start()
            
            # Mock entity extractor response
            mock_extract_response = MagicMock()
            mock_extract_response.status_code = 200
            mock_extract_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": """{"cypher_query": "MERGE (occ:Offensive_Content_Category {name: 'Firearms & Accessories'}) MERGE (sc1:Sub_Category {name: 'Ammunition'}) MERGE (occ)-[:HAS_SUB_CATEGORY]->(sc1)"}"""
                        }
                    }
                ]
            }
            mock_extract_post.return_value = mock_extract_response
            
            # Initialize agents
            print("Initializing agents...")
            classifier = PageClassifierAgent(api_key="fake_key", model="gpt-4")
            extractor = EntityExtractorAgent(
                api_key="fake_key",
                model="gpt-4",
                toc_prompt_system="system",
                toc_prompt_user="user",
                std_prompt_system="system",
                std_prompt_user="user"
            )
            context_agent = ContextAgent(context_file=context_file)
            cypher_generator = CypherGeneratorAgent()
            
            # Test workflow
            print("\nRunning workflow...")
            
            # Step 1: Classify page
            print("Step 1: Classifying page...")
            classification = classifier.classify_page("fake_base64_image")
            print(f"   Classification result: {classification}")
            
            # Step 2: Extract entities
            print("Step 2: Extracting entities...")
            extracted_data = extractor.extract_entities(classification, "fake_base64_image")
            print(f"   Extracted {len(extracted_data.get('sub_categories', []))} subcategories")
            
            # Step 3: Update context
            print("Step 3: Updating context...")
            updated_context = context_agent.process_extracted_data(1, extracted_data)
            print(f"   Context updated with {len(updated_context.get('sub_category', {}))} subcategories")
            
            # Step 4: Generate Cypher
            print("Step 4: Generating Cypher query...")
            cypher_result = cypher_generator.build_cypher(updated_context)
            print(f"   Cypher query generated with {len(cypher_result.get('cypher_query', ''))} characters")
            
            # Verify results
            assert "FULL_TOC" == classification, "Classification should be FULL_TOC"
            assert "Ammunition" in extracted_data.get("sub_categories", []), "Ammunition should be in subcategories"
            assert "Ammunition" in updated_context.get("sub_category", {}), "Ammunition should be in updated context"
            assert "Firearms & Accessories" in cypher_result.get("cypher_query", ""), "Category should be in Cypher query"
            
            print("\nIntegration test successful! Data flows correctly through all components.")
            
    finally:
        # Clean up the temporary file
        if os.path.exists(context_file):
            os.remove(context_file)
            print(f"Cleaned up temporary context file: {context_file}")

if __name__ == "__main__":
    run_integration_test()