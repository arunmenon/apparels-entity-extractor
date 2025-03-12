import os
import json
import sys
from entity_extractor import is_table_of_contents, gpt4_vision_compliance_extraction

def extract_subcategories_from_cypher(cypher_query):
    """Extract subcategories from a Cypher query string"""
    import re
    pattern = r"MERGE\s+\((?:sc\d+|s\d+):Sub_Category\s+\{name:\s*'([^']+)'\}\)"
    return re.findall(pattern, cypher_query)

def analyze_subcategory_format(subcategories):
    """Analyze the formatting consistency of extracted subcategories"""
    format_stats = {
        "total": len(subcategories),
        "with_hyphen_separator": 0,
        "with_colon_separator": 0,
        "with_ampersand": 0,
        "firearm_related": 0,
        "accessory_related": 0,
        "categories": set(),
        "avg_length": 0,
        "format_patterns": {}
    }
    
    # Count patterns
    total_length = 0
    for subcat in subcategories:
        total_length += len(subcat)
        
        # Check separators
        if " - " in subcat:
            format_stats["with_hyphen_separator"] += 1
        if ":" in subcat:
            format_stats["with_colon_separator"] += 1
        if "&" in subcat:
            format_stats["with_ampersand"] += 1
            
        # Check content
        if "firearm" in subcat.lower():
            format_stats["firearm_related"] += 1
        if "accessor" in subcat.lower():
            format_stats["accessory_related"] += 1
            
        # Identify category pattern
        main_category = None
        if " - " in subcat:
            main_category = subcat.split(" - ")[0]
        elif ":" in subcat:
            main_category = subcat.split(":")[0]
            
        if main_category:
            format_stats["categories"].add(main_category)
            
            # Count pattern occurrences
            if main_category in format_stats["format_patterns"]:
                format_stats["format_patterns"][main_category] += 1
            else:
                format_stats["format_patterns"][main_category] = 1
    
    # Calculate average length
    format_stats["avg_length"] = total_length / len(subcategories) if subcategories else 0
    
    # Convert to list for JSON serialization
    format_stats["categories"] = list(format_stats["categories"])
    
    return format_stats

def test_page_1_toc_extraction():
    """Test the TOC detection and extraction for page 1"""
    # Define paths
    image_path = "output_images/page_1.png"
    
    # Step 1: Check if page 1 is detected as TOC
    print("Step 1: Testing TOC detection for page 1...")
    is_toc = is_table_of_contents(image_path)
    print(f"Is page 1 a TOC page? {is_toc}")
    
    if not is_toc:
        print("ERROR: Page 1 was not detected as a TOC page!")
        return
    
    # Step 2: Run extraction using gpt4_vision_compliance_extraction
    print("Step 2: Running extraction for page 1...")
    extracted_data = gpt4_vision_compliance_extraction(image_path)
    
    if not extracted_data:
        print("ERROR: Failed to extract data from page 1")
        return
    
    try:
        # Load the extracted JSON
        if isinstance(extracted_data, str):
            extracted_json = json.loads(extracted_data)
        else:
            extracted_json = extracted_data
        
        # Check if it has a cypher_query field
        if "cypher_query" not in extracted_json:
            print("ERROR: Extracted data does not contain a cypher_query field")
            return
        
        # Extract subcategories from the cypher query
        cypher_query = extracted_json["cypher_query"]
        extracted_subcats = extract_subcategories_from_cypher(cypher_query)
        
        print(f"Extracted {len(extracted_subcats)} subcategories from page 1.")
        
        # Analyze the formatting and consistency
        format_stats = analyze_subcategory_format(extracted_subcats)
        
        # Report results
        print(f"\nSubcategory Analysis:")
        print(f"Total extracted subcategories: {format_stats['total']}")
        print(f"Average subcategory length: {format_stats['avg_length']:.1f} characters")
        print(f"Subcategories with hyphen separator: {format_stats['with_hyphen_separator']} ({format_stats['with_hyphen_separator']/format_stats['total']*100:.1f}%)")
        print(f"Subcategories with colon separator: {format_stats['with_colon_separator']} ({format_stats['with_colon_separator']/format_stats['total']*100:.1f}%)")
        print(f"Firearm-related subcategories: {format_stats['firearm_related']} ({format_stats['firearm_related']/format_stats['total']*100:.1f}%)")
        
        print("\nMain categories identified:")
        for category, count in sorted(format_stats["format_patterns"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {category}: {count} subcategories")
        
        print("\nExtracted subcategories:")
        for i, subcat in enumerate(sorted(extracted_subcats), 1):
            print(f"  {i}. {subcat}")
            
        # Write results to a file for review
        with open("toc_extraction_analysis.json", "w") as f:
            json.dump({
                "extracted_subcategories": sorted(extracted_subcats),
                "format_analysis": format_stats
            }, f, indent=2)
        
        print("\nFull analysis written to toc_extraction_analysis.json")
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in extracted data - {e}")
        print(f"Raw extracted data: {extracted_data[:200]}...")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    print("Testing TOC extraction for page 1...")
    test_page_1_toc_extraction()
    print("Test complete.")