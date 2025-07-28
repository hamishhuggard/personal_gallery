# gallery_server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from PIL import Image
import numpy as np

app = FastAPI()

# Mount static directories
# The full-size images will be served from /full_images
app.mount("/full_images", StaticFiles(directory="./imgs"), name="full_images")
# The small-size images (for gallery) will be served from /small_images
app.mount("/small_images", StaticFiles(directory="./imgs-small"), name="small_images")

# Templates for HTML rendering
templates = Jinja2Templates(directory="templates")

# Configuration
ORIGINAL_IMAGES_DIR = "./imgs"
SMALL_IMAGES_DIR = "./imgs-small"
IMAGES_PER_PAGE = 100 # Adjusted from 100 as per your request

# --- Helper Function to Get All Images ---
def get_all_image_paths(base_dir: str):
    """
    Scans a directory and its subdirectories for image files,
    returns a sorted list of relative paths.
    """
    base_path = Path(base_dir)
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    image_paths = []

    if not base_path.exists():
        print(f"Warning: Directory '{base_dir}' does not exist.")
        return []

    for root, _, files in os.walk(base_path):
        for file in files:
            if Path(file).suffix.lower() in image_extensions:
                # Store relative path for consistency
                relative_path = Path(root) / file
                image_paths.append(str(relative_path.relative_to(base_path)))

    # Sort alphabetically for consistent pagination
    image_paths.sort()
    return image_paths

# Cache the list of images to avoid re-scanning on every request
# In a production environment, you might want a more sophisticated caching
# or a mechanism to refresh this list if new images are added.
cached_image_list = get_all_image_paths(ORIGINAL_IMAGES_DIR)

# --- Helper Function to Crop Image ---
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
    try:
        # Open the image
        with Image.open(image_path) as img:
            # Convert to RGBA if not already
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Convert to numpy array for easier processing
            img_array = np.array(img)
            
            # Create a mask for non-white and non-transparent pixels
            # Non-white: not (R=255, G=255, B=255)
            # Non-transparent: A > 0
            non_white = ~((img_array[:, :, 0] == 255) & 
                         (img_array[:, :, 1] == 255) & 
                         (img_array[:, :, 2] == 255))
            non_transparent = img_array[:, :, 3] > 0
            
            # Combined mask: pixels that are both non-white and non-transparent
            content_mask = non_white & non_transparent
            
            # Find the bounding box of content
            if not np.any(content_mask):
                # No content found, return False
                return False
            
            # Get coordinates of non-zero elements
            rows = np.any(content_mask, axis=1)
            cols = np.any(content_mask, axis=0)
            
            # Find the boundaries
            top = np.where(rows)[0][0]
            bottom = np.where(rows)[0][-1]
            left = np.where(cols)[0][0]
            right = np.where(cols)[0][-1]
            
            # Calculate margin
            width = right - left
            height = bottom - top
            margin = max(margin_percent * width, margin_percent * height)
            margin = int(margin)
            
            # Apply margin (ensure we don't go outside image bounds)
            top = max(0, top - margin)
            bottom = min(img.height, bottom + margin)
            left = max(0, left - margin)
            right = min(img.width, right + margin)
            
            # Crop the image
            cropped_img = img.crop((left, top, right, bottom))
            
            # Save the cropped image back to the same path
            cropped_img.save(image_path, quality=95)
            
            return True
            
    except Exception as e:
        print(f"Error cropping image {image_path}: {e}")
        return False

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
@app.get("/gallery", response_class=HTMLResponse)
@app.get("/gallery/{page_num}", response_class=HTMLResponse)
async def read_gallery(request: Request, page_num: int = 1):
    """
    Serves the paginated image gallery.
    """
    if not cached_image_list:
        return templates.TemplateResponse("no_images.html", {"request": request, "message": "No images found in gallery."})

    total_images = len(cached_image_list)
    total_pages = (total_images + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE

    if not (1 <= page_num <= total_pages):
        raise HTTPException(status_code=404, detail="Page not found")

    start_index = (page_num - 1) * IMAGES_PER_PAGE
    end_index = min(start_index + IMAGES_PER_PAGE, total_images)

    images_on_page = cached_image_list[start_index:end_index]

    # Prepare image data for template
    gallery_items = []
    for img_relative_path in images_on_page:
        # Construct paths for both small and full-size images
        small_image_url = f"/small_images/{img_relative_path}"
        full_image_url = f"/full_images/{img_relative_path}"
        gallery_items.append({
            "small_url": small_image_url,
            "full_url": full_image_url,
            "title": Path(img_relative_path).name # Or extract title from metadata if available
        })

    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "gallery_items": gallery_items,
            "current_page": page_num,
            "total_pages": total_pages,
            "has_next": page_num < total_pages,
            "has_prev": page_num > 1,
            "next_page": page_num + 1,
            "prev_page": page_num - 1,
        }
    )

@app.get("/image/{image_path:path}", response_class=HTMLResponse)
async def read_single_image(request: Request, image_path: str):
    """
    Serves a single full-size image page.
    """
    # Check if the image path exists in our cached list for validation
    if image_path not in cached_image_list:
        raise HTTPException(status_code=404, detail="Image not found")

    # Find current image index and get navigation info
    current_index = cached_image_list.index(image_path)
    total_images = len(cached_image_list)
    
    # Get next and previous image paths
    next_image_path = cached_image_list[current_index + 1] if current_index < total_images - 1 else None
    prev_image_path = cached_image_list[current_index - 1] if current_index > 0 else None

    full_image_url = f"/full_images/{image_path}"
    
    return templates.TemplateResponse(
        "single_image.html",
        {
            "request": request,
            "image_url": full_image_url,
            "image_title": Path(image_path).name,
            "back_url": request.headers.get("referer", "/gallery"), # Go back to previous page or gallery root
            "next_image_path": next_image_path,
            "prev_image_path": prev_image_path,
            "current_index": current_index + 1,  # 1-based for display
            "total_images": total_images
        }
    )

@app.get("/crop/{image_path:path}")
async def crop_image(request: Request, image_path: str):
    """
    Crops an image to its content with a 10% margin and redirects back to the image view.
    """
    # Check if the image path exists in our cached list for validation
    if image_path not in cached_image_list:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Construct the full path to the image file
    full_image_path = os.path.join(ORIGINAL_IMAGES_DIR, image_path)
    
    # Perform the cropping
    success = crop_image_to_content(full_image_path)
    
    if success:
        # Redirect back to the image view
        return RedirectResponse(url=f"/image/{image_path}", status_code=302)
    else:
        # If cropping failed, redirect back with an error message
        # For now, just redirect back - you could add flash messages later
        return RedirectResponse(url=f"/image/{image_path}", status_code=302)