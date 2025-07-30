import os
from PIL import Image
import numpy as np

# Set this to False to disable cropping functionality
ENABLE_CROPPING = True  # <-- Set to False to comment out cropping

def crop_image_to_content(image_path: str, margin_percent: float = 0.1):
    """
    Crops an image to the bounding box of non-white and non-alpha pixels,
    with an additional margin around the content.
    Args:
        image_path: Path to the image file
        margin_percent: Percentage of margin to add (default 0.1 = 10%)
    Returns:
        bool: True if cropping was successful, False otherwise
    """
    if not ENABLE_CROPPING:
        print(f"Cropping is disabled. Skipping crop for {image_path}.")
        return False
    try:
        # Open the image
        with Image.open(image_path) as img:
            # Convert to RGBA if not already
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            # Convert to numpy array for easier processing
            img_array = np.array(img)
            # Create a mask for non-white and non-transparent pixels
            non_white = ~((img_array[:, :, 0] == 255) & 
                         (img_array[:, :, 1] == 255) & 
                         (img_array[:, :, 2] == 255))
            non_transparent = img_array[:, :, 3] > 0
            content_mask = non_white & non_transparent
            if not np.any(content_mask):
                # No content found, return False
                return False
            rows = np.any(content_mask, axis=1)
            cols = np.any(content_mask, axis=0)
            top = np.where(rows)[0][0]
            bottom = np.where(rows)[0][-1]
            left = np.where(cols)[0][0]
            right = np.where(cols)[0][-1]
            width = right - left
            height = bottom - top
            margin = max(margin_percent * width, margin_percent * height)
            margin = int(margin)
            top = max(0, top - margin)
            bottom = min(img.height, bottom + margin)
            left = max(0, left - margin)
            right = min(img.width, right + margin)
            cropped_img = img.crop((left, top, right, bottom))
            cropped_img.save(image_path, quality=95)
            return True
    except Exception as e:
        print(f"Error cropping image {image_path}: {e}")
        return False 