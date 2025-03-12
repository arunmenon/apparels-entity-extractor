"""
Enhanced entity extractor with context-aware extraction and subcategory normalization.
"""

import os
import json
import time
import logging
from difflib import SequenceMatcher

def get_most_recent_category(context):
    """Get the most recently seen category from context."""
    if not context["offensive_content_category"]:
        return None
    
    primary_category = None
    for category, info in context["offensive_content_category"].items():
        if info.get("is_primary"):
            primary_category = category
            break
    
    return primary_category

def get_recent_subcategories(context, limit=10):
    """Get the most recently seen subcategories from context."""
    if not context["sub_category"]:
        return []
    
    # Sort subcategories by last_seen time
    subcats = [(subcat, info) for subcat, info in context["sub_category"].items()]
    subcats.sort(key=lambda x: x[1].get("last_seen", 0), reverse=True)
    
    # Return the most recent subcategories
    return [subcat for subcat, _ in subcats[:limit]]

def get_toc_subcategories(context):
    """Extract all subcategories from TOC pages in the context."""
    toc_subcats = []
    
    for subcat, info in context["sub_category"].items():
        page_num = info.get("page", 0)
        
        # Check if this came from a TOC page - using a heuristic
        # We consider low page numbers (1-3) with many subcategories to be TOC pages
        if page_num <= 3 and "toc" in str(page_num).lower():
            toc_subcats.append(subcat)
    
    return toc_subcats

def similarity_score(a, b):
    """Calculate similarity score between two strings."""
    if not a or not b:
        return 0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(subcategory, reference_list, threshold=0.7):
    """Find the best matching subcategory from the reference list."""
    best_match = None
    best_score = 0
    
    for ref_subcat in reference_list:
        score = similarity_score(subcategory, ref_subcat)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = ref_subcat
    
    return best_match, best_score

def create_context_aware_prompt(system_prompt, user_prompt, context):
    """Create a context-aware prompt by injecting context information."""
    current_category = get_most_recent_category(context)
    recent_subcategories = get_recent_subcategories(context)
    toc_subcategories = get_toc_subcategories(context)
    
    # Add context information to user prompt
    context_info = ""
    if current_category:
        context_info += f"Based on previous pages, the current category appears to be: {current_category}\n\n"
    
    if toc_subcategories:
        context_info += "CRITICAL: Here are the OFFICIAL SUBCATEGORIES from the Table of Contents:\n"
        for i, subcat in enumerate(toc_subcategories[:20], 1):  # Limit to top 20 to avoid too much text
            context_info += f"- {subcat}\n"
        
        if len(toc_subcategories) > 20:
            context_info += f"- ... and {len(toc_subcategories) - 20} more\n"
        
        context_info += "\nIMPORTANT INSTRUCTIONS FOR SUBCATEGORIES:\n"
        context_info += "1. ONLY extract subcategories that appear as CLEAR SECTION HEADERS in the page\n"
        context_info += "2. ONLY use subcategories from the list above or ones that closely match them\n"
        context_info += "3. If you don't see a clear subcategory header, DO NOT create one - the content may be continuing from a previous page\n"
        context_info += "4. A page should typically have only 1-2 subcategories, not more\n"
        context_info += "5. Never extract subcategories from examples, image captions, or reference sections\n\n"
    
    if recent_subcategories:
        context_info += "Recent subcategories from previous pages include:\n"
        for subcat in recent_subcategories:
            context_info += f"- {subcat}\n"
        context_info += "\n"
    
    context_info += "If you see content related to these categories or subcategories, include them in your extraction.\n"
    context_info += "When the page doesn't explicitly mention a category, use the current category from context.\n\n"
    
    enhanced_user = context_info + user_prompt
    
    return system_prompt, enhanced_user

def normalize_subcategories(extracted_data, context, threshold=0.7, max_subcats=2):
    """
    Normalize extracted subcategories against TOC subcategories.
    
    Args:
        extracted_data: The data extracted from a page
        context: The entity context
        threshold: Minimum similarity score for matching
        max_subcats: Maximum number of subcategories to keep per page
    """
    if not extracted_data or "sub_categories" not in extracted_data:
        return extracted_data
    
    # Check what type of page we're dealing with
    is_details_page = False
    is_toc_page = False
    
    # We infer this from the name pattern in the workflow
    page_name = str(extracted_data.get("_page_name", ""))
    if "_details" in page_name:
        is_details_page = True
        max_subcats = 1
        print("Limiting to 1 subcategory for details page")
    elif "_toc" in page_name or "TOC" in page_name:
        is_toc_page = True
        # For TOC pages, we don't limit the number of subcategories
        max_subcats = 1000  # Effectively no limit
        print("TOC page detected - extracting all subcategories")
    
    # Get reference subcategories from TOC
    toc_subcats = get_toc_subcategories(context)
    if not toc_subcats:
        # Try to get from any source as fallback
        toc_subcats = list(context["sub_category"].keys())
    
    # Make a copy of the data to modify
    normalized_data = extracted_data.copy()
    extracted_subcats = normalized_data.get("sub_categories", [])
    
    # For TOC pages, we don't normalize against reference subcategories
    # since the TOC page itself defines the reference list
    if is_toc_page:
        return normalized_data
    
    # For other pages, normalize subcategories against TOC list
    if toc_subcats:
        # Normalize each subcategory
        normalized_subcats = []
        for subcat in extracted_subcats:
            best_match, score = find_best_match(subcat, toc_subcats, threshold)
            
            if best_match:
                print(f"Normalized subcategory: '{subcat}' → '{best_match}' (similarity: {score:.2f})")
                normalized_subcats.append(best_match)
            else:
                # Keep original if no good match
                normalized_subcats.append(subcat)
        
        # Enforce maximum subcategory limit for regular and details pages
        if len(normalized_subcats) > max_subcats:
            print(f"Too many subcategories ({len(normalized_subcats)}), limiting to {max_subcats}")
            
            # If we're on a details page, just keep the first one
            if is_details_page:
                normalized_subcats = normalized_subcats[:1]
            else:
                # For regular pages, keep the most relevant subcategories
                subcats_to_keep = []
                
                # First priority: exact matches with TOC subcategories
                for subcat in normalized_subcats:
                    if subcat in toc_subcats and len(subcats_to_keep) < max_subcats:
                        subcats_to_keep.append(subcat)
                
                # Second priority: fill remaining slots with other subcategories
                for subcat in normalized_subcats:
                    if subcat not in subcats_to_keep and len(subcats_to_keep) < max_subcats:
                        subcats_to_keep.append(subcat)
                
                normalized_subcats = subcats_to_keep
        
        # Replace with normalized subcategories
        normalized_data["sub_categories"] = normalized_subcats
    
    return normalized_data

def enrich_extraction_with_context(extracted_data, context):
    """Enrich extraction results with context when entities are missing."""
    if not extracted_data:
        extracted_data = {}
    
    enriched = extracted_data.copy()
    
    # First, normalize subcategories against TOC list
    enriched = normalize_subcategories(enriched, context)
    
    # Add the category from context - the model doesn't extract it anymore
    current_category = get_most_recent_category(context)
    if current_category:
        enriched["offensive_content_category"] = current_category
    
    # If no subcategories are found, but there are rules or guidelines,
    # add subcategories from context that might be related
    if (not enriched.get("sub_categories") and 
        (enriched.get("guidelines") or enriched.get("rules"))):
        # Get recent subcategories
        recent_subcats = get_recent_subcategories(context, limit=3)
        if recent_subcats:
            enriched["sub_categories"] = recent_subcats
            print(f"Enriched with {len(recent_subcats)} subcategories from context")
    
    # Ensure all required fields exist
    if "sub_categories" not in enriched:
        enriched["sub_categories"] = []
    if "guidelines" not in enriched:
        enriched["guidelines"] = []
    if "rules" not in enriched:
        enriched["rules"] = []
    
    return enriched