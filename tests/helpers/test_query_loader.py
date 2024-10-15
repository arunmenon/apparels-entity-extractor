import unittest
import os
import json
import sys

# Add the helpers directory to the system path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'helpers'))

from helpers import query_loader  # Import query_loader from helpers

class TestQueryLoader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load test cases from the test_cases.json file inside the current directory
        config_file = os.path.join(os.path.dirname(__file__), 'test_cases.json')
        with open(config_file, 'r') as f:
            cls.test_cases = json.load(f)

    def test_escape_special_characters(self):
        # Loop through each test case from config for escape_special_characters
        for case in self.test_cases['escape_special_characters']:
            result = query_loader.escape_special_characters(case['input'])
            self.assertEqual(result, case['expected'], f"Failed for input: {case['input']}")

    def test_sanitize_query(self):
        # Loop through each test case from config for sanitize_query
        for case in self.test_cases['sanitize_query']:
            self.maxDiff = None
            result = query_loader.sanitize_query(case['input'])
            self.assertEqual(result, case['expected'], f"Failed for input: {case['input']}")

if __name__ == '__main__':
    unittest.main()
