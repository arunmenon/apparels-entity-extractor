#!/usr/bin/env python3
"""
Test script for the QueryValidator component.
"""

import os
import sys
import unittest
import logging

# Add the parent directory to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(parent_dir)

from agentic_workflow.graph_rag.agents.query_validator import QueryValidator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestQueryValidator(unittest.TestCase):
    """Test suite for the QueryValidator."""
    
    def setUp(self):
        """Set up the test environment."""
        self.validator = QueryValidator()
    
    def test_multiple_where_clauses(self):
        """Test fixing multiple WHERE clauses."""
        query = """
        MATCH path = (c:Category)-[:PARENT_OF*]->(sc:Subcategory)<-[:MAY_VIOLATE]-(pt:ProductType) 
        WHERE (pt)-[:MAY_VIOLATE]->(sc) AND (pt)-[:MAY_VIOLATE]->(sc) 
        WHERE r.confidence_score >= 0.4
        RETURN [node IN nodes(path) | coalesce(node.label, labels(node)[0])] AS Hierarchy
        """
        
        fixed_query, is_valid, error = self.validator.validate_and_fix(query)
        
        self.assertTrue(is_valid)
        self.assertIn("AND r.confidence_score", fixed_query)
        self.assertNotIn("WHERE r.confidence_score", fixed_query)
    
    def test_undefined_relationship_variable(self):
        """Test fixing undefined relationship variables."""
        query = """
        MATCH (pt:ProductType)-[:MAY_VIOLATE]->(sc:Subcategory)
        WHERE r.confidence_score >= 0.4
        RETURN pt.name, sc.name
        """
        
        fixed_query, is_valid, error = self.validator.validate_and_fix(query)
        
        self.assertTrue(is_valid)
        self.assertIn("[r:MAY_VIOLATE]", fixed_query)
        
    def test_missing_parentheses(self):
        """Test fixing missing parentheses."""
        query = """
        MATCH (pt:ProductType)-[:MAY_VIOLATE]->(sc:Subcategory
        WHERE pt.name = 'Test'
        RETURN pt.name, sc.name
        """
        
        fixed_query, is_valid, error = self.validator.validate_and_fix(query)
        
        self.assertTrue(is_valid)
        self.assertIn(")", fixed_query.strip()[-1:])
    
    def test_duplicate_relationship_conditions(self):
        """Test fixing duplicate relationship conditions."""
        query = """
        MATCH (pt:ProductType)-[:MAY_VIOLATE]->(sc:Subcategory)
        WHERE (pt)-[:MAY_VIOLATE]->(sc) AND (pt)-[:MAY_VIOLATE]->(sc)
        RETURN pt.name, sc.name
        """
        
        fixed_query, is_valid, error = self.validator.validate_and_fix(query)
        
        self.assertTrue(is_valid)
        self.assertNotIn("AND (pt)-[:MAY_VIOLATE]->(sc)", fixed_query)
    
    def test_complex_hierarchical_path_query(self):
        """Test fixing a complex hierarchical path query."""
        query = """
        MATCH path = (c:Category)-[:PARENT_OF*]->(sc:Subcategory)<-[:MAY_VIOLATE]-(pt:ProductType)
        WHERE (pt)-[:MAY_VIOLATE]->(sc) WHERE r.confidence_score >= 0.4
        RETURN [node IN nodes(path) | labels(node)[0]] AS Hierarchy
        """
        
        fixed_query, is_valid, error = self.validator.validate_and_fix(query)
        
        self.assertTrue(is_valid)
        self.assertIn("AND r.confidence_score", fixed_query)
        self.assertNotIn("WHERE r.confidence_score", fixed_query)
        
    def test_query_with_aliased_relationship(self):
        """Test fixing aliased relationship queries."""
        query = """
        MATCH (p:ProductType)-[rel:MAY_VIOLATE]->(s:Subcategory)
        WHERE rel.confidence_score >= 0.4
        RETURN p.name, s.name, rel.confidence_score
        """
        
        fixed_query, is_valid, error = self.validator.validate_and_fix(query)
        
        self.assertTrue(is_valid)
        self.assertEqual(query.strip(), fixed_query.strip())
        self.assertIsNone(error)

if __name__ == "__main__":
    unittest.main()