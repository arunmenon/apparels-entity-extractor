#!/usr/bin/env python3
"""
Script to evaluate TOC extraction against ground truth.
"""

import os
import json
import argparse
from pathlib import Path
import pandas as pd
from tabulate import tabulate
from difflib import SequenceMatcher

def load_data(extracted_file, ground_truth_file):
    """Load extracted data and ground truth."""
    with open(extracted_file, 'r') as f:
        extracted = json.load(f)
    
    with open(ground_truth_file, 'r') as f:
        ground_truth = json.load(f)
    
    return extracted, ground_truth

def similarity_score(a, b):
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def evaluate_extraction(extracted, ground_truth, threshold=0.85):
    """Evaluate extraction against ground truth using fuzzy matching."""
    # Extract subcategories
    extracted_subcats = extracted.get("sub_categories", [])
    if isinstance(ground_truth, dict):
        gt_subcats = ground_truth.get("subcategories", [])
    else:
        gt_subcats = ground_truth
    
    # Match subcategories
    matches = []
    matched_gt = set()
    matched_ext = set()
    
    for i, ext_cat in enumerate(extracted_subcats):
        best_match = None
        best_score = 0
        
        for j, gt_cat in enumerate(gt_subcats):
            score = similarity_score(ext_cat, gt_cat)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = (j, gt_cat, score)
        
        if best_match:
            j, gt_cat, score = best_match
            matches.append((ext_cat, gt_cat, score))
            matched_gt.add(j)
            matched_ext.add(i)
    
    # Find missing and hallucinated categories
    missing = [(j, gt_subcats[j]) for j in range(len(gt_subcats)) if j not in matched_gt]
    hallucinated = [(i, extracted_subcats[i]) for i in range(len(extracted_subcats)) if i not in matched_ext]
    
    # Calculate metrics
    if len(extracted_subcats) > 0:
        precision = len(matches) / len(extracted_subcats)
    else:
        precision = 0
        
    if len(gt_subcats) > 0:
        recall = len(matches) / len(gt_subcats)
    else:
        recall = 0
        
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0
    
    results = {
        "matches": matches,
        "missing": missing,
        "hallucinated": hallucinated,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "match_count": len(matches),
        "total_extracted": len(extracted_subcats),
        "total_ground_truth": len(gt_subcats)
    }
    
    return results

def print_evaluation_report(results, threshold):
    """Print evaluation report."""
    print("\n=== TOC EXTRACTION EVALUATION ===")
    print(f"Fuzzy matching threshold: {threshold}")
    print(f"\nMETRICS:")
    print(f"Precision: {results['precision']:.2f}")
    print(f"Recall: {results['recall']:.2f}")
    print(f"F1 Score: {results['f1_score']:.2f}")
    print(f"Matches: {results['match_count']} / {results['total_ground_truth']}")
    
    print(f"\nMATCHED CATEGORIES ({len(results['matches'])}):")
    if results['matches']:
        for i, (ext, gt, score) in enumerate(results['matches'], 1):
            print(f"{i}. Extracted: \"{ext}\" ↔ Ground Truth: \"{gt}\" (similarity: {score:.2f})")
    else:
        print("None")
    
    print(f"\nMISSING CATEGORIES ({len(results['missing'])}):")
    if results['missing']:
        for i, (idx, cat) in enumerate(results['missing'], 1):
            print(f"{i}. {cat}")
    else:
        print("None")
    
    print(f"\nHALLUCINATED CATEGORIES ({len(results['hallucinated'])}):")
    if results['hallucinated']:
        for i, (idx, cat) in enumerate(results['hallucinated'], 1):
            print(f"{i}. {cat}")
    else:
        print("None")

def save_evaluation_report(results, output_dir, output_file):
    """Save evaluation report to file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nEvaluation report saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Evaluate TOC extraction against ground truth')
    parser.add_argument('--extracted', required=True, help='Path to extracted TOC JSON file')
    parser.add_argument('--ground-truth', required=True, help='Path to ground truth JSON file')
    parser.add_argument('--threshold', type=float, default=0.85, help='Fuzzy matching threshold (0-1)')
    parser.add_argument('--output-dir', default='experimental/reporting/outputs', help='Directory to save reports')
    parser.add_argument('--output-file', default='toc_evaluation.json', help='Filename for evaluation report')
    
    args = parser.parse_args()
    
    # Load data
    extracted, ground_truth = load_data(args.extracted, args.ground_truth)
    
    # Evaluate extraction
    results = evaluate_extraction(extracted, ground_truth, args.threshold)
    
    # Print report
    print_evaluation_report(results, args.threshold)
    
    # Save report
    save_evaluation_report(results, args.output_dir, args.output_file)

if __name__ == "__main__":
    main()