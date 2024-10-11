import unittest
import query_loader

class TestQueryLoader(unittest.TestCase):

    def test_escape_special_characters(self):
        # Test simple escaping of single quotes
        test_cases = [
            ("Women's Apparel", "Women\\'s Apparel"),  # Single quote escaping
            ("Men's Wear", "Men\\'s Wear")             # Another example of escaping
        ]

        for test_input, expected_output in test_cases:
            result = query_loader.escape_special_characters(test_input)
            self.assertEqual(result, expected_output)

    def test_sanitize_query(self):
        # Test query sanitization with single quotes inside the query
        test_query = "CREATE (n1:Apparel_Category {name: 'Women's Apparel'})"
        expected_sanitized_query = "CREATE (n1:Apparel_Category {name: 'Women\\'s Apparel'})"

        sanitized_query = query_loader.sanitize_query(test_query)
        self.assertEqual(sanitized_query, expected_sanitized_query)

if __name__ == '__main__':
    unittest.main()
