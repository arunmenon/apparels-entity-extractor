"""
Taxonomy REST API - Provides endpoints for querying the compliance taxonomy.

This module implements a FastAPI service that allows:
1. Querying the compliance taxonomy
2. Searching for categories, areas, and relationships
3. Getting detailed information about specific entities
4. Exporting statistics and graph data
"""

import os
import json
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field

# Import the service layer
from experimental.graph_ops.taxonomy_service import TaxonomyService

# Create FastAPI app
app = FastAPI(
    title="Compliance Taxonomy API",
    description="API for querying the compliance taxonomy and relationships",
    version="1.0.0"
)

# Models for responses
class Category(BaseModel):
    """Model for a product category."""
    name: str
    compliance_areas_count: int
    
class ComplianceArea(BaseModel):
    """Model for a compliance area."""
    name: str
    category: str
    regulations_count: int
    standards_count: int
    criteria_count: int
    relationships_count: int

class Relationship(BaseModel):
    """Model for a relationship between compliance areas."""
    source_area: str
    source_category: str
    target_area: str
    target_category: str
    relationship_type: str
    description: str

class Regulation(BaseModel):
    """Model for a regulation."""
    name: str
    citation: str
    
class Standard(BaseModel):
    """Model for a standard."""
    name: str
    citation: str
    
class TaxonomyStats(BaseModel):
    """Model for taxonomy statistics."""
    categories: int
    compliance_areas: int
    regulations: int
    standards: int
    criteria: int
    relationships: int
    most_regulated_areas: List[Dict[str, Any]]
    most_connected_areas: List[Dict[str, Any]]

# Create service instance
def get_taxonomy_service():
    """Create and return the taxonomy service."""
    # Locate the taxonomy file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    taxonomy_path = os.path.join(base_dir, 'taxonomy', 'compliance_taxonomy.json')
    
    # Create service
    service = TaxonomyService()
    
    # Load the taxonomy
    if taxonomy_path not in service.taxonomy_cache:
        service.load_taxonomy(taxonomy_path)
        
    return service

# API Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Compliance Taxonomy API",
        "version": "1.0.0",
        "description": "API for querying the compliance taxonomy and relationships"
    }

@app.get("/categories", response_model=List[Category])
async def get_categories(service: TaxonomyService = Depends(get_taxonomy_service)):
    """Get all product categories."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    categories = []
    for category in taxonomy.get("categories", []):
        categories.append({
            "name": category.get("name", ""),
            "compliance_areas_count": len(category.get("complianceAreas", []))
        })
    
    return categories

@app.get("/categories/{category_name}", response_model=Dict[str, Any])
async def get_category(
    category_name: str = Path(..., description="Name of the category"),
    service: TaxonomyService = Depends(get_taxonomy_service)
):
    """Get details for a specific category."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    category = service.get_category_by_name(taxonomy, category_name)
    if not category:
        raise HTTPException(status_code=404, detail=f"Category '{category_name}' not found")
    
    # Format the response
    compliance_areas = []
    for area in category.get("complianceAreas", []):
        compliance_areas.append({
            "name": area.get("name", ""),
            "regulations_count": len(area.get("regulations", [])),
            "standards_count": len(area.get("standards", [])),
            "criteria_count": len(area.get("criteria", [])),
            "relationships_count": len(area.get("relationships", []))
        })
    
    return {
        "name": category.get("name", ""),
        "compliance_areas": compliance_areas
    }

@app.get("/compliance-areas/{area_name}", response_model=Dict[str, Any])
async def get_compliance_area(
    area_name: str = Path(..., description="Name of the compliance area"),
    service: TaxonomyService = Depends(get_taxonomy_service)
):
    """Get details for a specific compliance area."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    # Find the compliance area in any category
    area_details = None
    area_category = None
    
    for category in taxonomy.get("categories", []):
        for area in category.get("complianceAreas", []):
            if area.get("name") == area_name:
                area_details = area
                area_category = category.get("name")
                break
        if area_details:
            break
    
    if not area_details:
        raise HTTPException(status_code=404, detail=f"Compliance area '{area_name}' not found")
    
    # Format the response
    regulations = [
        {
            "name": reg.get("name", ""),
            "citation": reg.get("citation", "")
        }
        for reg in area_details.get("regulations", [])
    ]
    
    standards = [
        {
            "name": std.get("name", ""),
            "citation": std.get("citation", "")
        }
        for std in area_details.get("standards", [])
    ]
    
    relationships = []
    for rel in area_details.get("relationships", []):
        rel_type = ""
        target = ""
        
        if "impacts" in rel:
            rel_type = "impacts"
            target = rel["impacts"]
        elif "overlaps" in rel:
            rel_type = "overlaps"
            target = rel["overlaps"]
        elif "relatedTo" in rel:
            rel_type = "relatedTo"
            target = rel["relatedTo"]
        
        relationships.append({
            "type": rel_type,
            "target": target,
            "description": rel.get("description", "")
        })
    
    return {
        "name": area_name,
        "category": area_category,
        "regulations": regulations,
        "standards": standards,
        "criteria": area_details.get("criteria", []),
        "relationships": relationships
    }

@app.get("/related/{area_name}", response_model=List[Dict[str, Any]])
async def get_related_areas(
    area_name: str = Path(..., description="Name of the compliance area"),
    service: TaxonomyService = Depends(get_taxonomy_service)
):
    """Get areas related to a specific compliance area."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    related_areas = service.get_related_areas(taxonomy, area_name)
    
    if not related_areas:
        raise HTTPException(status_code=404, detail=f"No related areas found for '{area_name}'")
    
    # Format the response
    formatted_related = []
    for related in related_areas:
        formatted_related.append({
            "area": related["area"]["name"],
            "category": related["category"],
            "relationship_type": related["relation_type"],
            "description": related["description"]
        })
    
    return formatted_related

@app.get("/search", response_model=Dict[str, List[Dict[str, str]]])
async def search_taxonomy(
    query: str = Query(..., description="Search query term"),
    service: TaxonomyService = Depends(get_taxonomy_service)
):
    """Search the taxonomy for the given term."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    query = query.lower()
    
    categories = []
    compliance_areas = []
    regulations = []
    standards = []
    criteria = []
    
    # Search in categories
    for category in taxonomy.get("categories", []):
        category_name = category.get("name", "")
        if query in category_name.lower():
            categories.append({
                "name": category_name,
                "type": "category"
            })
        
        # Search in compliance areas
        for area in category.get("complianceAreas", []):
            area_name = area.get("name", "")
            if query in area_name.lower():
                compliance_areas.append({
                    "name": area_name,
                    "category": category_name,
                    "type": "compliance_area"
                })
            
            # Search in regulations
            for reg in area.get("regulations", []):
                reg_name = reg.get("name", "")
                citation = reg.get("citation", "")
                if query in reg_name.lower() or query in citation.lower():
                    regulations.append({
                        "name": reg_name,
                        "citation": citation,
                        "area": area_name,
                        "category": category_name,
                        "type": "regulation"
                    })
            
            # Search in standards
            for std in area.get("standards", []):
                std_name = std.get("name", "")
                citation = std.get("citation", "")
                if query in std_name.lower() or query in citation.lower():
                    standards.append({
                        "name": std_name,
                        "citation": citation,
                        "area": area_name,
                        "category": category_name,
                        "type": "standard"
                    })
            
            # Search in criteria
            for criterion in area.get("criteria", []):
                if query in criterion.lower():
                    criteria.append({
                        "description": criterion[:100] + "..." if len(criterion) > 100 else criterion,
                        "area": area_name,
                        "category": category_name,
                        "type": "criterion"
                    })
    
    return {
        "categories": categories,
        "compliance_areas": compliance_areas,
        "regulations": regulations,
        "standards": standards,
        "criteria": criteria
    }

@app.get("/statistics", response_model=TaxonomyStats)
async def get_statistics(service: TaxonomyService = Depends(get_taxonomy_service)):
    """Get statistics about the taxonomy."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    stats = service.generate_taxonomy_statistics(taxonomy)
    return stats

@app.get("/export/cypher", response_model=Dict[str, Any])
async def export_cypher(service: TaxonomyService = Depends(get_taxonomy_service)):
    """Export the taxonomy as Cypher statements for Neo4j."""
    taxonomy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 'taxonomy', 'compliance_taxonomy.json')
    taxonomy = service.taxonomy_cache.get(taxonomy_path)
    
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    
    statements = service.export_cypher_statements(taxonomy)
    
    return {
        "statement_count": len(statements),
        "statements": statements
    }

# Run the API
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("taxonomy_api:app", host="0.0.0.0", port=8000, reload=True)