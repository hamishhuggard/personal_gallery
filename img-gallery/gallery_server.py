# gallery_server.py
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from utils.crop_utils import crop_image_to_content
from db import init_db, get_session, ImageMeta, Tag
import subprocess
import sys

app = FastAPI()
init_db()

# Mount static directories
# The full-size images will be served from /full_images
app.mount("/full_images", StaticFiles(directory="./imgs-medium"), name="full_images")
#app.mount("/full_images", StaticFiles(directory="./imgs-small"), name="full_images")
# The small-size images (for gallery) will be served from /small_images
app.mount("/small_images", StaticFiles(directory="./imgs-small"), name="small_images")

# Templates for HTML rendering
templates = Jinja2Templates(directory="templates")

# Configuration
ORIGINAL_IMAGES_DIR = "./imgs"
SMALL_IMAGES_DIR = "./imgs-small"
IMAGES_PER_PAGE = 100 # Adjusted from 100 as per your request
ADMIN_MODE = True  # Set to False to disable admin features

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

def refresh_images():
    """
    Run the downsizing script to create medium and small images, then refresh the cache.
    """
    try:
        # Run downsizing for medium images (600px)
        print("Creating medium images (600px)...")
        result1 = subprocess.run([
            sys.executable, "create_downsized_images.py",
            "--input", "./imgs",
            "--output", "./imgs-medium", 
            "--max_dim", "600"
        ], capture_output=True, text=True, cwd=".")
        
        if result1.returncode != 0:
            print(f"Error creating medium images: {result1.stderr}")
            return False
            
        # Run downsizing for small images (300px)
        print("Creating small images (300px)...")
        result2 = subprocess.run([
            sys.executable, "create_downsized_images.py",
            "--input", "./imgs",
            "--output", "./imgs-small",
            "--max_dim", "300"
        ], capture_output=True, text=True, cwd=".")
        
        if result2.returncode != 0:
            print(f"Error creating small images: {result2.stderr}")
            return False
            
        # Refresh the cached image list
        global cached_image_list
        cached_image_list = get_all_image_paths(ORIGINAL_IMAGES_DIR)
        
        print("Image refresh completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during image refresh: {e}")
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
            "admin_mode": ADMIN_MODE,
        }
    )

@app.get("/tags", response_class=HTMLResponse)
async def list_tags(request: Request):
    """
    Lists all available tags with image counts.
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        tags = session.query(Tag).options(joinedload(Tag.images)).all()
        
        # Get image count for each tag
        tag_data = []
        for tag in tags:
            image_count = len(tag.images)
            tag_data.append({
                "name": tag.name,
                "count": image_count
            })
        
        # Sort by count (descending) then by name
        tag_data.sort(key=lambda x: (-x["count"], x["name"]))
    finally:
        session.close()
    
    return templates.TemplateResponse(
        "tags_list.html",
        {
            "request": request,
            "tags": tag_data,
            "admin_mode": ADMIN_MODE,
        }
    )

@app.get("/tag/{tag_name}", response_class=HTMLResponse)
@app.get("/tag/{tag_name}/{page_num}", response_class=HTMLResponse)
async def tag_gallery(request: Request, tag_name: str, page_num: int = 1):
    """
    Shows a gallery of images with a specific tag.
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        tag = session.query(Tag).options(joinedload(Tag.images)).filter_by(name=tag_name).first()
        
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        # Get all images with this tag
        tagged_images = [img.path for img in tag.images if img.path in cached_image_list]
        
        if not tagged_images:
            return templates.TemplateResponse("no_images.html", {
                "request": request, 
                "message": f"No images found with tag '{tag_name}'."
            })
        
        total_images = len(tagged_images)
        total_pages = (total_images + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE
        
        if not (1 <= page_num <= total_pages):
            raise HTTPException(status_code=404, detail="Page not found")
        
        start_index = (page_num - 1) * IMAGES_PER_PAGE
        end_index = min(start_index + IMAGES_PER_PAGE, total_images)
        
        images_on_page = tagged_images[start_index:end_index]
        
        # Prepare image data for template
        gallery_items = []
        for img_relative_path in images_on_page:
            small_image_url = f"/small_images/{img_relative_path}"
            full_image_url = f"/full_images/{img_relative_path}"
            gallery_items.append({
                "small_url": small_image_url,
                "full_url": full_image_url,
                "title": Path(img_relative_path).name
            })
    finally:
        session.close()
    
    return templates.TemplateResponse(
        "tag_gallery.html",
        {
            "request": request,
            "tag_name": tag_name,
            "gallery_items": gallery_items,
            "current_page": page_num,
            "total_pages": total_pages,
            "has_next": page_num < total_pages,
            "has_prev": page_num > 1,
            "next_page": page_num + 1,
            "prev_page": page_num - 1,
            "admin_mode": ADMIN_MODE,
        }
    )

@app.get("/image/{image_path:path}", response_class=HTMLResponse)
async def read_single_image(request: Request, image_path: str, from_page: int = None):
    """
    Serves a single full-size image page.
    """
    if image_path not in cached_image_list:
        raise HTTPException(status_code=404, detail="Image not found")

    current_index = cached_image_list.index(image_path)
    total_images = len(cached_image_list)
    next_image_path = cached_image_list[current_index + 1] if current_index < total_images - 1 else None
    prev_image_path = cached_image_list[current_index - 1] if current_index > 0 else None
    full_image_url = f"/full_images/{image_path}"

    # Get metadata from DB with tags eagerly loaded
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        meta = session.query(ImageMeta).options(joinedload(ImageMeta.tags)).filter_by(path=image_path).first()
        
        if meta:
            image_title = meta.title if meta.title else Path(image_path).stem
            image_description = meta.description or None
            image_date = meta.date or None
            image_tags = [tag.name for tag in meta.tags] if meta.tags else []
            image_drawings_count = meta.drawings_count or 1
        else:
            image_title = Path(image_path).stem
            image_description = None
            image_date = None
            image_tags = []
            image_drawings_count = 1
    finally:
        session.close()

    if from_page is not None:
        back_url = f"/gallery/{from_page}"
    else:
        referer = request.headers.get("referer", "")
        if referer and ("/gallery" in referer or referer.endswith("/")):
            back_url = referer
        else:
            back_url = "/gallery"

    return templates.TemplateResponse(
        "single_image.html",
        {
            "request": request,
            "image_url": full_image_url,
            "image_title": image_title,
            "image_description": image_description,
            "image_date": image_date,
            "image_tags": image_tags,
            "image_drawings_count": image_drawings_count,
            "back_url": back_url,
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

@app.get("/admin/edit/{page_num}", response_class=HTMLResponse)
async def edit_gallery_page(request: Request, page_num: int):
    if not ADMIN_MODE:
        raise HTTPException(status_code=403, detail="Admin mode is disabled.")

    # Get images for this page
    total_images = len(cached_image_list)
    total_pages = (total_images + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE
    if not (1 <= page_num <= total_pages):
        raise HTTPException(status_code=404, detail="Page not found")
    start_index = (page_num - 1) * IMAGES_PER_PAGE
    end_index = min(start_index + IMAGES_PER_PAGE, total_images)
    images_on_page = cached_image_list[start_index:end_index]

    # Fetch metadata for these images with tags eagerly loaded
    session = get_session()
    try:
        # Use joinedload to eagerly load the tags relationship
        from sqlalchemy.orm import joinedload
        meta_list = session.query(ImageMeta).options(joinedload(ImageMeta.tags)).filter(ImageMeta.path.in_(images_on_page)).all()
        meta_dict = {meta.path: meta for meta in meta_list}
        
        # Get all available tags for the tag selector
        all_tags = [tag.name for tag in session.query(Tag).order_by(Tag.name).all()]
        
        # Prepare data for template - extract all data we need while session is open
        edit_items = []
        for img_path in images_on_page:
            meta = meta_dict.get(img_path)
            if meta:
                edit_items.append({
                    "path": img_path,
                    "small_url": f"/small_images/{img_path}",
                    "full_url": f"/full_images/{img_path}",
                    "title": meta.title if meta.title else Path(img_path).stem,
                    "description": meta.description if meta.description else "",
                    "is_public": meta.is_public if meta.is_public is not None else True,
                    "date": meta.date if meta.date else "",
                    "drawings_count": meta.drawings_count if meta.drawings_count else 1,
                    "tags": ", ".join([tag.name for tag in meta.tags]) if meta.tags else "",
                })
            else:
                # No metadata exists for this image, create default entry
                edit_items.append({
                    "path": img_path,
                    "small_url": f"/small_images/{img_path}",
                    "full_url": f"/full_images/{img_path}",
                    "title": Path(img_path).stem,
                    "description": "",
                    "is_public": True,
                    "date": "",
                    "drawings_count": 1,
                    "tags": "",
                })
    finally:
        session.close()

    return templates.TemplateResponse(
        "edit_gallery_page.html",
        {
            "request": request,
            "edit_items": edit_items,
            "all_tags": all_tags,
            "current_page": page_num,
            "total_pages": total_pages,
        }
    )

@app.post("/admin/edit/{page_num}", response_class=HTMLResponse)
async def save_gallery_page_edits(request: Request, page_num: int):
    if not ADMIN_MODE:
        raise HTTPException(status_code=403, detail="Admin mode is disabled.")

    form = await request.form()
    num_items = int(form.get("num_items", 0))

    session = get_session()
    try:
        for i in range(num_items):
            path = form.get(f"path_{i}")
            title = form.get(f"title_{i}")
            description = form.get(f"description_{i}")
            is_public = form.get(f"is_public_{i}") == "1"
            date = form.get(f"date_{i}")
            drawings_count = int(form.get(f"drawings_count_{i}", 1))
            tags_str = form.get(f"tags_{i}", "")

            # Upsert logic
            meta = session.query(ImageMeta).filter_by(path=path).first()
            if not meta:
                meta = ImageMeta(path=path)
                session.add(meta)
            meta.title = title
            meta.description = description
            meta.is_public = is_public
            meta.date = date
            meta.drawings_count = drawings_count

            # Handle tags
            if tags_str.strip():
                tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
                meta.tags = []
                for tag_name in tag_names:
                    tag = session.query(Tag).filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        session.add(tag)
                    meta.tags.append(tag)
            else:
                meta.tags = []

        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        session.close()

    # After saving, redirect back to the edit page
    return RedirectResponse(url=f"/admin/edit/{page_num}", status_code=303)

@app.post("/refresh")
async def refresh_gallery():
    """
    Refresh the gallery by running the downsizing script and updating the cache.
    """
    if not ADMIN_MODE:
        raise HTTPException(status_code=403, detail="Admin mode is disabled.")
    
    success = refresh_images()
    
    if success:
        return RedirectResponse(url="/gallery", status_code=303)
    else:
        raise HTTPException(status_code=500, detail="Failed to refresh images")
