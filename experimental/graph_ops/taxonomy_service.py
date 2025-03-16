"""
Taxonomy Service - Manages taxonomy data and graph operations.

This module provides a clean service layer for taxonomy operations:
1. Loading taxonomies from different sources
2. Converting to standardized internal format
3. Querying taxonomy data 
4. Updating taxonomy structures
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaxonomyService:
    """Service for managing taxonomy data and operations."""
    
    def __init__(self, graph_client=None):
        """
        Initialize the taxonomy service.
        
        Args:
            graph_client: Optional graph database client
        """
        self.graph_client = graph_client
        self.taxonomy_cache = {}
    
    def load_taxonomy(self, source_path: str) -> Dict:
        """
        Load a taxonomy from a file.
        
        Args:
            source_path: Path to the taxonomy file
            
        Returns:
            Dict: The loaded taxonomy
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Taxonomy file not found: {source_path}")
        
        try:
            with open(source_path, 'r') as f:
                taxonomy = json.load(f)
                
            # Store in cache
            self.taxonomy_cache[source_path] = taxonomy
            
            logger.info(f"Loaded taxonomy from {source_path}")
            return taxonomy
            
        except Exception as e:
            logger.error(f"Error loading taxonomy: {e}")
            raise
    
    def get_category_by_name(self, taxonomy: Dict, name: str) -> Optional[Dict]:
        """
        Find a category by name.
        
        Args:
            taxonomy: The taxonomy to search
            name: The category name to find
            
        Returns:
            Dict or None: The matching category if found
        """
        for category in taxonomy.get("categories", []):
            if category.get("name") == name:
                return category
        return None
    
    def get_compliance_area(self, category: Dict, area_name: str) -> Optional[Dict]:
        """
        Find a compliance area by name within a category.
        
        Args:
            category: The category to search
            area_name: The compliance area name to find
            
        Returns:
            Dict or None: The matching compliance area if found
        """
        for area in category.get("complianceAreas", []):
            if area.get("name") == area_name:
                return area
        return None
    
    def get_related_areas(self, taxonomy: Dict, area_name: str) -> List[Dict]:
        """
        Find all compliance areas related to the given area.
        
        Args:
            taxonomy: The taxonomy to search
            area_name: The compliance area name
            
        Returns:
            List[Dict]: Related compliance areas
        """
        related_areas = []
        
        # Search all categories and their compliance areas
        for category in taxonomy.get("categories", []):
            for area in category.get("complianceAreas", []):
                if area.get("name") == area_name:
                    # Found our target area, now find related areas
                    for relation in area.get("relationships", []):
                        relation_type = None
                        target_area = None
                        
                        if "impacts" in relation:
                            relation_type = "impacts"
                            target_area = relation["impacts"]
                        elif "overlaps" in relation:
                            relation_type = "overlaps"
                            target_area = relation["overlaps"]
                        elif "relatedTo" in relation:
                            relation_type = "relatedTo"
                            target_area = relation["relatedTo"]
                            
                        if target_area:
                            # Find the target area in the taxonomy
                            for c in taxonomy.get("categories", []):
                                for a in c.get("complianceAreas", []):
                                    if a.get("name") == target_area:
                                        related_areas.append({
                                            "category": c.get("name"),
                                            "area": a,
                                            "relation_type": relation_type,
                                            "description": relation.get("description", "")
                                        })
        
        return related_areas
    
    def export_cypher_statements(self, taxonomy: Dict) -> List[str]:
        """
        Generate Cypher statements to create the taxonomy in Neo4j.
        
        Args:
            taxonomy: The taxonomy to export
            
        Returns:
            List[str]: Cypher statements
        """
        statements = []
        
        # Create unique constraint if it doesn't exist
        statements.append(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE"
        )
        
        statements.append(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:ComplianceArea) REQUIRE (a.name, a.category) IS NODE KEY"
        )
        
        # Add categories
        for category in taxonomy.get("categories", []):
            category_name = category.get("name", "")
            if not category_name:
                continue
                
            # Create category node
            statements.append(
                f"MERGE (c:Category {{name: \"{self._escape_quotes(category_name)}\"}}) "
                f"RETURN c"
            )
            
            # Add compliance areas
            for area in category.get("complianceAreas", []):
                area_name = area.get("name", "")
                if not area_name:
                    continue
                    
                # Create compliance area node
                statements.append(
                    f"MATCH (c:Category {{name: \"{self._escape_quotes(category_name)}\"}}) "
                    f"MERGE (a:ComplianceArea {{name: \"{self._escape_quotes(area_name)}\", category: \"{self._escape_quotes(category_name)}\"}}) "
                    f"MERGE (c)-[:HAS_COMPLIANCE_AREA]->(a) "
                    f"RETURN a"
                )
                
                # Add regulations
                for regulation in area.get("regulations", []):
                    reg_name = regulation.get("name", "")
                    citation = regulation.get("citation", "")
                    
                    if not reg_name:
                        continue
                        
                    statements.append(
                        f"MATCH (a:ComplianceArea {{name: \"{self._escape_quotes(area_name)}\", category: \"{self._escape_quotes(category_name)}\"}}) "
                        f"MERGE (r:Regulation {{name: \"{self._escape_quotes(reg_name)}\"}}) "
                        f"SET r.citation = \"{self._escape_quotes(citation)}\" "
                        f"MERGE (a)-[:HAS_REGULATION]->(r) "
                        f"RETURN r"
                    )
                
                # Add standards
                for standard in area.get("standards", []):
                    std_name = standard.get("name", "")
                    citation = standard.get("citation", "")
                    
                    if not std_name:
                        continue
                        
                    statements.append(
                        f"MATCH (a:ComplianceArea {{name: \"{self._escape_quotes(area_name)}\", category: \"{self._escape_quotes(category_name)}\"}}) "
                        f"MERGE (s:Standard {{name: \"{self._escape_quotes(std_name)}\"}}) "
                        f"SET s.citation = \"{self._escape_quotes(citation)}\" "
                        f"MERGE (a)-[:HAS_STANDARD]->(s) "
                        f"RETURN s"
                    )
                
                # Add criteria
                for criterion in area.get("criteria", []):
                    if not criterion:
                        continue
                    
                    # Limit criterion length to avoid overly long Cypher statements
                    criterion_text = criterion[:500] + ("..." if len(criterion) > 500 else "")
                    
                    statements.append(
                        f"MATCH (a:ComplianceArea {{name: \"{self._escape_quotes(area_name)}\", category: \"{self._escape_quotes(category_name)}\"}}) "
                        f"MERGE (c:Criterion {{description: \"{self._escape_quotes(criterion_text)}\"}}) "
                        f"MERGE (a)-[:HAS_CRITERION]->(c) "
                        f"RETURN c"
                    )
        
        # Add relationships between compliance areas
        for category in taxonomy.get("categories", []):
            category_name = category.get("name", "")
            
            for area in category.get("complianceAreas", []):
                source_area_name = area.get("name", "")
                
                for relationship in area.get("relationships", []):
                    relation_type = None
                    target_area_name = None
                    description = relationship.get("description", "")
                    
                    if "impacts" in relationship:
                        relation_type = "IMPACTS"
                        target_area_name = relationship["impacts"]
                    elif "overlaps" in relationship:
                        relation_type = "OVERLAPS_WITH"
                        target_area_name = relationship["overlaps"]
                    elif "relatedTo" in relationship:
                        relation_type = "RELATED_TO"
                        target_area_name = relationship["relatedTo"]
                    
                    if relation_type and target_area_name:
                        statements.append(
                            f"MATCH (source:ComplianceArea {{name: \"{self._escape_quotes(source_area_name)}\", category: \"{self._escape_quotes(category_name)}\"}}) "
                            f"MATCH (target:ComplianceArea {{name: \"{self._escape_quotes(target_area_name)}\"}}) "
                            f"MERGE (source)-[r:{relation_type}]->(target) "
                            f"SET r.description = \"{self._escape_quotes(description)}\" "
                            f"RETURN r"
                        )
        
        return statements
    
    def generate_taxonomy_statistics(self, taxonomy: Dict) -> Dict:
        """
        Generate statistics about a taxonomy.
        
        Args:
            taxonomy: The taxonomy to analyze
            
        Returns:
            Dict: Statistics about the taxonomy
        """
        stats = {
            "categories": 0,
            "compliance_areas": 0,
            "regulations": 0,
            "standards": 0,
            "criteria": 0,
            "relationships": 0,
            "category_sizes": [],
            "most_regulated_areas": [],
            "most_connected_areas": []
        }
        
        area_regulations = {}
        area_connections = {}
        
        # Count items
        for category in taxonomy.get("categories", []):
            stats["categories"] += 1
            category_name = category.get("name", "")
            
            compliance_areas = category.get("complianceAreas", [])
            stats["compliance_areas"] += len(compliance_areas)
            
            stats["category_sizes"].append({
                "category": category_name,
                "compliance_areas": len(compliance_areas)
            })
            
            for area in compliance_areas:
                area_name = area.get("name", "")
                regulations = area.get("regulations", [])
                standards = area.get("standards", [])
                criteria = area.get("criteria", [])
                relationships = area.get("relationships", [])
                
                stats["regulations"] += len(regulations)
                stats["standards"] += len(standards) 
                stats["criteria"] += len(criteria)
                stats["relationships"] += len(relationships)
                
                # Track regulations per area
                area_regulations[f"{category_name}:{area_name}"] = len(regulations)
                
                # Track connections per area
                area_connections[f"{category_name}:{area_name}"] = len(relationships)
        
        # Find most regulated areas
        stats["most_regulated_areas"] = [
            {"area": k.split(":", 1)[1], "category": k.split(":", 1)[0], "regulations": v}
            for k, v in sorted(area_regulations.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        # Find most connected areas
        stats["most_connected_areas"] = [
            {"area": k.split(":", 1)[1], "category": k.split(":", 1)[0], "connections": v}
            for k, v in sorted(area_connections.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        return stats
    
    def _escape_quotes(self, text: str) -> str:
        """
        Escape double quotes for Cypher statements.
        
        Args:
            text: The text to escape
            
        Returns:
            str: The escaped text
        """
        return text.replace('"', '\\"')