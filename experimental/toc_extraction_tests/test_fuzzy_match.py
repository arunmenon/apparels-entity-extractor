#!/usr/bin/env python3
"""
Testing script with fuzzy matching for better validation
"""

import os
import time
import json
import difflib
import argparse
from difflib import SequenceMatcher

def normalize_text(text):
    """Normalize text for better matching"""
    return text.lower().replace("-", " ").replace("&", "and").replace(":", " ").replace("/", " ")

def fuzzy_match(a, b, threshold=0.85):
    """Check if two strings match with fuzzy matching"""
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio() >= threshold

def find_best_match(item, candidates, threshold=0.85):
    """Find the best fuzzy match for an item in a list of candidates"""
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        score = SequenceMatcher(None, normalize_text(item), normalize_text(candidate)).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    
    return best_match, best_score

def main():
    """Compare extraction results with ground truth using fuzzy matching"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test TOC extraction with fuzzy matching")
    parser.add_argument("--extraction", "-e", 
                        help="Path to the extraction JSON file",
                        default="page_1_test_output.json")
    parser.add_argument("--threshold", "-t", type=float, default=0.85,
                        help="Fuzzy matching threshold (0.0-1.0, default: 0.85)")
    args = parser.parse_args()
    
    # Set up variables
    extraction_path = args.extraction
    threshold = args.threshold
    
    print(f"\n=== FUZZY MATCHING EVALUATION (threshold={threshold}) ===")
    
    # Check if the extraction file exists
    if not os.path.exists(extraction_path):
        print(f"Error: Extraction file not found at {extraction_path}")
        return 1
    
    # Load the extraction results
    with open(extraction_path, 'r') as f:
        extraction_data = json.load(f)
        extracted_subcats = extraction_data.get("sub_categories", [])
    
    # Load ground truth
    with open("actual_ground_truth.json", "r") as f:
        ground_truth_data = json.load(f)
        ground_truth = ground_truth_data.get("subcategories", [])
    
    print(f"Loaded {len(extracted_subcats)} extracted items and {len(ground_truth)} ground truth items")
    
    # Perform fuzzy matching
    matched_pairs = []
    matched_ground_truth = set()
    matched_extracted = set()
    
    # For each ground truth item, find the best match in extracted items
    for gt_item in ground_truth:
        best_match, score = find_best_match(gt_item, extracted_subcats, threshold)
        if best_match:
            matched_pairs.append((gt_item, best_match, score))
            matched_ground_truth.add(gt_item)
            matched_extracted.add(best_match)
    
    # Calculate metrics
    missing = set(ground_truth) - matched_ground_truth
    hallucinated = set(extracted_subcats) - matched_extracted
    
    precision = len(matched_pairs) / len(extracted_subcats) if extracted_subcats else 0
    recall = len(matched_pairs) / len(ground_truth) if ground_truth else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Print results
    print("\n=== FUZZY MATCHING RESULTS ===")
    print(f"Ground truth items: {len(ground_truth)}")
    print(f"Extracted items: {len(extracted_subcats)}")
    print(f"Matched pairs: {len(matched_pairs)}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    
    # Show matched pairs
    if matched_pairs:
        print("\n=== MATCHED PAIRS ===")
        for gt_item, ext_item, score in sorted(matched_pairs, key=lambda x: x[2], reverse=True)[:10]:
            print(f"  [{score:.2f}] \"{gt_item}\" ⟷ \"{ext_item}\"")
        if len(matched_pairs) > 10:
            print(f"  ... and {len(matched_pairs) - 10} more matches")
    
    # Show missing items
    if missing:
        print(f"\n=== MISSING ITEMS ({len(missing)}) ===")
        for item in sorted(missing)[:10]:
            print(f"  - {item}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    
    # Show hallucinated items
    if hallucinated:
        print(f"\n=== HALLUCINATED ITEMS ({len(hallucinated)}) ===")
        for item in sorted(hallucinated)[:10]:
            print(f"  + {item}")
        if len(hallucinated) > 10:
            print(f"  ... and {len(hallucinated) - 10} more")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())