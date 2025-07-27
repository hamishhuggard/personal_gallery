# gallery_server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

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

    full_image_url = f"/full_images/{image_path}"
    
    return templates.TemplateResponse(
        "single_image.html",
        {
            "request": request,
            "image_url": full_image_url,
            "image_title": Path(image_path).name,
            "back_url": request.headers.get("referer", "/gallery") # Go back to previous page or gallery root
        }
    )