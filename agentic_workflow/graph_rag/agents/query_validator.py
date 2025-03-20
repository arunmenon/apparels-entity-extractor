"""
Query Validator - Module for validating and fixing Cypher queries.

This module provides functionality for:
1. Validating Cypher queries before execution
2. Fixing common syntax and semantic errors
3. Providing feedback on query issues
4. Ensuring safe and correct query execution
"""

import re
import logging
from typing import Tuple, List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QueryValidator:
    """Validates and fixes Cypher queries to prevent common errors."""
    
    def __init__(self):
        # Initialize common error patterns and their fixes
        self.error_fixes = [
            # Multiple WHERE clauses - replace second WHERE with AND
            (r'WHERE\s+(.+?)\s+WHERE\s+', r'WHERE \1 AND '),
            
            # Add relationship variable if missing
            (r'(\[)(:)([^\]]+)(\])', r'\1r\2\3\4'),
            
            # Fix undefined relationship variables in property access
            (r'([^a-zA-Z0-9_])([a-zA-Z][a-zA-Z0-9_]*)\.([a-zA-Z][a-zA-Z0-9_]*)\s+', 
             self._fix_undefined_relationship_var),
            
            # Missing closing parentheses
            (r'\([^()]*?$', self._balance_parentheses),
            
            # Missing alias in path patterns
            (r'MATCH\s+path\s*=\s*\(([^:)]+):', r'MATCH path = (n:\1:'),
            
            # Remove duplicate relationship conditions
            (r'(WHERE|AND)\s+\((\w+)\)-\[.*?\]->\((\w+)\)\s+AND\s+\(\2\)-\[.*?\]->\(\3\)', 
             r'\1 (\2)-[]->\3'),
             
            # Fix incorrectly aliased relationship variables
            (r'(MATCH.*?)-\[(\w+):([^\]]+)\]->.*?WHERE.*?\2\.(\w+)', 
             self._ensure_relationship_var_defined)
        ]
    
    def _fix_undefined_relationship_var(self, match: re.Match) -> str:
        """
        Fix undefined relationship variables in property access.
        
        Looks for references to relationship properties without the relationship
        being properly defined in the MATCH clause.
        """
        prefix = match.group(1)
        rel_var = match.group(2)
        prop = match.group(3)
        
        # Check if this is likely a relationship variable
        if rel_var.lower() == 'r' or rel_var.lower().startswith('rel'):
            return f"{prefix}{rel_var}.{prop} "
        
        # Otherwise, leave as is
        return match.group(0)
    
    def _balance_parentheses(self, match: re.Match) -> str:
        """Add missing closing parentheses."""
        fragment = match.group(0)
        open_count = fragment.count('(')
        close_count = fragment.count(')')
        missing = open_count - close_count
        
        if missing <= 0:
            return fragment
            
        return fragment + ')' * missing
    
    def _ensure_relationship_var_defined(self, match: re.Match) -> str:
        """Ensure relationship variables are properly defined in the MATCH clause."""
        match_clause = match.group(1)
        rel_var = match.group(2)
        rel_type = match.group(3)
        prop = match.group(4)
        
        # Check if relationship variable is already defined
        if f"-[{rel_var}:" in match_clause:
            return match.group(0)
        
        # Fix by replacing unaliased relationship with aliased one
        fixed_match = match_clause.replace(f"-[:{rel_type}]->", f"-[{rel_var}:{rel_type}]->")
        return f"{fixed_match}-[{rel_var}:{rel_type}]->.*?WHERE.*?{rel_var}.{prop}"
    
    def validate_and_fix(self, query: str) -> Tuple[str, bool, Optional[str]]:
        """
        Validate and fix common Cypher query issues.
        
        Args:
            query: The Cypher query to validate
            
        Returns:
            Tuple of (fixed_query, is_valid, error_message)
        """
        if not query or not isinstance(query, str):
            return query, False, "Invalid query: Query must be a non-empty string"
        
        fixed_query = query
        original_query = query
        
        # Apply all error fixes
        for pattern, replacement in self.error_fixes:
            if callable(replacement):
                # For complex replacements that need a function
                matches = list(re.finditer(pattern, fixed_query))
                for match in reversed(matches):  # Process from end to start to maintain positions
                    replacement_text = replacement(match)
                    fixed_query = fixed_query[:match.start()] + replacement_text + fixed_query[match.end():]
            else:
                # For simple regex replacements
                fixed_query = re.sub(pattern, replacement, fixed_query)
        
        # Log changes if query was modified
        if fixed_query != original_query:
            logger.info(f"Modified query before execution:")
            logger.info(f"Original: {original_query}")
            logger.info(f"Fixed: {fixed_query}")
            
            # If major modifications were made, add a warning
            if len(fixed_query) / len(original_query) < 0.8 or len(fixed_query) / len(original_query) > 1.2:
                logger.warning("Significant modifications were made to the query - verify results carefully")
        
        # Check for known problematic patterns
        issues = self._check_known_issues(fixed_query)
        if issues:
            logger.warning(f"Potential issues in query: {', '.join(issues)}")
            return fixed_query, True, f"Query has potential issues: {', '.join(issues)}"
            
        return fixed_query, True, None
    
    def _check_known_issues(self, query: str) -> List[str]:
        """Check for known problematic patterns that might not be syntax errors."""
        issues = []
        
        # Check for missing relationship variable with property access
        rel_prop_access = re.search(r'WHERE.*?\w+\.\w+', query)
        if rel_prop_access and not re.search(r'MATCH.*?\[(\w+):', query):
            issues.append("Possible undefined relationship variable")
            
        # Check for cartesian products (missing relationships between patterns)
        if query.count('MATCH ') > 1 and 'WHERE' not in query:
            issues.append("Possible cartesian product (multiple MATCH without WHERE)")
            
        # Check for possibly inefficient patterns
        if 'OPTIONAL MATCH' in query and query.count('OPTIONAL MATCH') > 2:
            issues.append("Multiple OPTIONAL MATCH clauses may cause performance issues")
            
        # Check for unbounded variable-length paths that might be expensive
        if re.search(r'\[.*\*.*\]', query) and not re.search(r'\[.*\*\d+\.\.', query):
            issues.append("Unbounded variable-length path may cause performance issues")
        
        return issues