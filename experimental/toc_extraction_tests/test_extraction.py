#!/usr/bin/env python3
"""
Simple test script to verify the extraction process for a single page.
"""

import os
import json
import sys
import time
import logging
from utils import encode_image
from agentic_workflow.entity_extractor import EntityExtractorAgent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Test entity extraction on a single page."""
    logger = logging.getLogger("test_extraction")
    logger.info("Starting TOC extraction performance test")
    
    print("\n=== TOC EXTRACTION PERFORMANCE TEST ===")
    total_start_time = time.time()
    
    # Load prompts
    print("Loading prompts...")
    with open("toc_system_prompt.txt", "r") as f:
        toc_system_prompt = f.read()
    with open("toc_extraction_prompt.txt", "r") as f:
        toc_user_prompt = f.read()
    with open("entity_system_prompt.txt", "r") as f:
        std_system_prompt = f.read()
    with open("entity_extraction_prompt.txt", "r") as f:
        std_user_prompt = f.read()
        
    logger.info("Prompts loaded successfully")
    
    # Set up extractor
    print("Initializing entity extractor...")
    api_key = os.getenv('OPENAI_API_KEY', '')
    model = "gpt-4o"  # Force latest model for best extraction
    
    extractor = EntityExtractorAgent(
        api_key=api_key,
        model=model,
        toc_prompt_system=toc_system_prompt,
        toc_prompt_user=toc_user_prompt,
        std_prompt_system=std_system_prompt,
        std_prompt_user=std_user_prompt
    )
    
    # Load image
    print("Loading image...")
    img_path = "output_images/page_1.png"
    base64_img = encode_image(img_path)
    
    # Extract as TOC page
    print("\nExtracting entities from TOC page...")
    api_start = time.time()
    extraction_result = extractor.extract_entities("FULL_TOC", base64_img)
    api_duration = time.time() - api_start
    print(f"API extraction completed in {api_duration:.2f} seconds")
    
    # Print result
    print("\nExtraction result:")
    print(f"Category: {extraction_result.get('offensive_content_category', 'None')}")
    print(f"Subcategories ({len(extraction_result.get('sub_categories', []))}):")
    for idx, subcat in enumerate(extraction_result.get('sub_categories', []), 1):
        print(f"  {idx}. {subcat}")
    
    # Save result
    with open("test_extraction_output.json", "w") as f:
        json.dump(extraction_result, f, indent=2)
    
    print(f"\nComplete result saved to test_extraction_output.json")
    
    # Compare with ground truth (for testing)
    ground_truth = [
        "Ammo Reloading - Dies, Shells Holders & Plates",
        "Ammunition",
        "Ammunition: .223 and 5.56",
        "Ammunition Production",
        "Armorer's Wrenches",
        "Assault Rifles",
        "Cane Guns",
        "Concealed Carrying Weapon Holsters, Belly Bands, & Similar Items",
        "Firearms: Handguns/Pistols",
        "Firearms: Magazines and Clips",
        "Firearm Accessories",
        "Firearm Accessories: Flashlights",
        "Firearm Accessories: Handgun Sights",
        "Firearm Accessories: M-LOK & KeyMod",
        "Firearm Accessories: Magazine UPCs",
        "Firearm Accessories: Optics, Scopes, and Sights",
        "Firearm Accessories: Sight Adapter Plates",
        "Firearm Components",
        "Firearm Accessories: Tannerite Targets",
        "Firearm Item ID, UPC, GTIN",
        "Firearm Pistol Grips",
        "Flare Guns",
        "Flechette Darts",
        "Fuel Trap / Solvent Filter / Solvent Trap",
        "Grenades",
        "Gun Cases",
        "Gun Powder",
        "Homeland Security Chemical of Interest (COI)",
        "Human Targets",
        "ITAR Regulated",
        "Modern Sporting Rifle (MSR)",
        "Muzzle Devices & Silencers/Suppressors",
        "Muzzleloaders",
        "Pinfire Guns",
        "Powerheads",
        "Scopes with Lasers",
        "Shoulder Harnesses",
        "Snap Caps, Training 'Dummy' Ammunition, Laser Boresights, Headspace Gauges",
        "Sniper Rifles",
        "Sports South LLC (Firearm Catch-All Rule)",
        "Tactical - Duty Holsters",
        "Tactical Gear: Range Bags",
        "Tactical Gear: Thigh Rigs",
        "Tactical Slings",
        "Toothpick Crossbow",
        "Vinyl Wrap for Firearms",
        "Weapons Conversion Blueprints/Instructions/Manuals"
    ]
    
    # Calculate accuracy
    extracted = set(extraction_result.get('sub_categories', []))
    truth = set(ground_truth)
    
    # Find missing and hallucinated items
    missing = truth - extracted
    hallucinated = extracted - truth
    
    correct = len(truth.intersection(extracted))
    recall = correct / len(truth) if truth else 0
    precision = correct / len(extracted) if extracted else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Print validation results
    print("\n=== VALIDATION RESULTS ===")
    print(f"Ground truth items: {len(truth)}")
    print(f"Extracted items: {len(extracted)}")
    print(f"Correctly extracted: {correct}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")
    print(f"F1 Score: {f1:.2f}")
    
    if missing:
        print("\nMissing items:")
        for item in sorted(missing):
            print(f"  - {item}")
    
    if hallucinated:
        print("\nHallucinated items:")
        for item in sorted(hallucinated):
            print(f"  - {item}")
    
    # Print total execution time
    total_duration = time.time() - total_start_time
    print(f"\nTotal script execution time: {total_duration:.2f} seconds")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())