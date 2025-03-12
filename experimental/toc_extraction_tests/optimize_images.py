#!/usr/bin/env python3
"""
Optimize images for faster vision API processing
"""

import os
from PIL import Image
import glob

def optimize_image(input_path, output_path, max_size=1600, quality=90):
    """
    Resize and compress an image for faster API processing
    
    Args:
        input_path: Path to the original image
        output_path: Path to save the optimized image
        max_size: Maximum dimension (width or height)
        quality: JPEG quality (0-100)
    """
    try:
        # Open the image
        img = Image.open(input_path)
        
        # Calculate new dimensions while maintaining aspect ratio
        width, height = img.size
        if width > height:
            if width > max_size:
                new_width = max_size
                new_height = int(height * (max_size / width))
        else:
            if height > max_size:
                new_height = max_size
                new_width = int(width * (max_size / height))
            else:
                new_width, new_height = width, height
        
        # Resize the image
        if new_width != width or new_height != height:
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save the optimized image
        img.save(output_path, "JPEG", quality=quality, optimize=True)
        
        # Get file sizes
        original_size = os.path.getsize(input_path) / 1024  # KB
        optimized_size = os.path.getsize(output_path) / 1024  # KB
        reduction = (1 - (optimized_size / original_size)) * 100
        
        print(f"Optimized {input_path} → {output_path}")
        print(f"  Original: {original_size:.1f} KB, Optimized: {optimized_size:.1f} KB")
        print(f"  Size reduction: {reduction:.1f}%, New dimensions: {new_width}x{new_height}")
        
        return True
    
    except Exception as e:
        print(f"Error optimizing {input_path}: {str(e)}")
        return False

def main():
    """
    Optimize all images in the output_images directory
    """
    # Create optimized directory if it doesn't exist
    optimized_dir = "optimized_images"
    os.makedirs(optimized_dir, exist_ok=True)
    
    # Get all images in the output_images directory
    input_dir = "output_images"
    image_paths = glob.glob(os.path.join(input_dir, "*.png"))
    
    if not image_paths:
        print(f"No images found in {input_dir}")
        return
    
    print(f"Found {len(image_paths)} images to optimize")
    success_count = 0
    
    # Process each image
    for input_path in image_paths:
        filename = os.path.basename(input_path)
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(optimized_dir, f"{base_name}.jpg")
        
        if optimize_image(input_path, output_path):
            success_count += 1
    
    print(f"\nOptimization complete: {success_count}/{len(image_paths)} images processed")
    print(f"Optimized images saved to {optimized_dir}/")

if __name__ == "__main__":
    main()