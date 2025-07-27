# resize_images.py
import os
from pathlib import Path
from PIL import Image
from tqdm import tqdm
import argparse
import stat # For getting file info

def resize_images(input_dir: str, output_dir: str, max_dim: int, force_overwrite: bool = False):
    """
    Scans an input directory for images, resizes them to a specified maximum dimension,
    and saves them to an output directory, maintaining directory structure.
    It skips images that have already been resized and whose original has not been
    modified since the last resize, unless force_overwrite is True.

    Args:
        input_dir (str): The root directory containing original images.
        output_dir (str): The directory where resized images will be saved.
        max_dim (int): The maximum dimension (width or height) for the resized image.
                       The other dimension will be scaled proportionally.
        force_overwrite (bool): If True, re-processes all images regardless of modification time.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists() or not input_path.is_dir():
        print(f"Error: Input directory '{input_dir}' does not exist or is not a directory.")
        return

    # Create the output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    all_image_files = []

    print(f"Scanning '{input_dir}' for images...")
    for root, _, files in os.walk(input_path):
        for file in files:
            if Path(file).suffix.lower() in image_extensions:
                all_image_files.append(Path(root) / file)

    if not all_image_files:
        print(f"No image files found in '{input_dir}'.")
        return

    print(f"Found {len(all_image_files)} image files. Starting resizing...")

    # Use tqdm for a progress bar
    for original_file_path in tqdm(all_image_files, desc="Resizing Images"):
        relative_path = original_file_path.relative_to(input_path)
        output_file_path = output_path / relative_path

        # Create parent directories in the output_dir if they don't exist
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if output file exists and if original is older than resized output
        if output_file_path.exists() and not force_overwrite:
            try:
                # Get modification times (mtime)
                original_mtime = original_file_path.stat().st_mtime
                output_mtime = output_file_path.stat().st_mtime

                # If the original file has not been modified since the resized one was created, skip.
                # Adding a small buffer (e.g., 1 second) for potential filesystem time precision issues.
                if original_mtime <= output_mtime + 1:
                    continue # Skip this file, it's already up-to-date
            except OSError as e:
                tqdm.write(f"Warning: Could not get mtime for {original_file_path} or {output_file_path}: {e}")
                # If we can't get mtime, we'll proceed with processing to be safe, or just skip if output exists.
                # For this case, we'll just skip to prevent errors halting the script.
                continue # Skip if mtime check fails

        try:
            with Image.open(original_file_path) as img:
                width, height = img.size

                # Calculate new dimensions while maintaining aspect ratio
                if width > height:
                    new_width = max_dim
                    new_height = int(max_dim * (height / width))
                else:
                    new_height = max_dim
                    new_width = int(max_dim * (width / height))

                # If the image is already smaller than the target max_dim, just copy it (no resize needed)
                # This prevents upscaling or unnecessary re-encoding of small images.
                if width <= max_dim and height <= max_dim:
                    # In this case, we're just copying. Use shutil for efficiency.
                    import shutil
                    shutil.copy2(original_file_path, output_file_path)
                    continue # Move to next file
                
                # Resize the image using LANCZOS for high quality downscaling
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)

                # Save the resized image. Use original format if possible, or convert to JPEG for web.
                # Consider saving as JPEG with quality for web, even if original was PNG, for smaller size.
                # For this example, we'll try to preserve original format, but override with JPEG for common types.
                output_format = resized_img.format
                if original_file_path.suffix.lower() in {'.png', '.gif'}:
                    # Keep PNG for transparency or sharp graphics if needed
                    # Otherwise, use JPEG for photos/drawings to save space
                    if original_file_path.suffix.lower() == '.png':
                        resized_img.save(output_file_path, format='PNG', optimize=True)
                    else: # GIF
                        resized_img.save(output_file_path, format='GIF')
                else:
                    # For JPG, BMP, TIFF, WebP, save as JPEG or WebP for smaller size
                    resized_img.save(output_file_path, format='JPEG', quality=85) # Adjust quality as needed

        except Exception as e:
            tqdm.write(f"Error processing {original_file_path}: {e}")

    print("Image resizing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resize images in a directory and its subdirectories, handling updates."
    )
    parser.add_argument("--input", "-i", default="./imgs",
                        help="The input directory containing original images (default: ./imgs)")
    parser.add_argument("--output", "-o", default="./imgs-small",
                        help="The output directory for resized images (default: ./imgs-small)")
    parser.add_argument("--max_dim", "-d", type=int, default=300,
                        help="The maximum dimension (width or height) for resized images (default: 300 pixels)")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force re-processing of all images, ignoring modification times.")

    args = parser.parse_args()

    # --- Dummy Image Creation for Testing (Optional) ---
    # This block helps create test data if your directories are empty.
    # You can comment it out after initial testing.
    if not Path(args.input).exists() or not any(Path(args.input).iterdir()):
        print(f"Input directory '{args.input}' is empty or does not exist. Creating dummy image files...")
        try:
            from PIL import Image, ImageDraw
            Path(args.input).mkdir(parents=True, exist_ok=True)
            for i in range(5):
                # Create a few dummy images in subdirectories
                img_subdir = Path(args.input) / f"drawings_set_{i % 2}"
                img_subdir.mkdir(parents=True, exist_ok=True)
                img_path = img_subdir / f"drawing_{i+1}.png"

                img_width = 1200 + i * 50 # Varying sizes
                img_height = 900 + i * 20
                
                img = Image.new('RGB', (img_width, img_height), color=(73, 109, 137 + i * 10))
                d = ImageDraw.Draw(img)
                d.text((img_width * 0.1, img_height * 0.1), f"Artwork {i+1}", fill=(255, 255, 0), font_size=40)
                img.save(img_path)
            
            # Create a JPG dummy for testing format conversion
            jpg_path = Path(args.input) / "subdir_jpg" / "example_painting.jpg"
            jpg_path.parent.mkdir(parents=True, exist_ok=True)
            jpg_img = Image.new('RGB', (1500, 1000), color=(200, 150, 100))
            d_jpg = ImageDraw.Draw(jpg_img)
            d_jpg.text((100, 100), "JPG Example", fill=(0, 0, 0), font_size=50)
            jpg_img.save(jpg_path)

            print(f"Dummy images created in '{args.input}'.")
            if not args.force:
                print("Run the script again without '--create-dummy' or with '-f' to process them.")
                exit()
        except ImportError:
            print("Pillow not installed. Cannot create dummy images.")
            print(f"Please install Pillow (`pip install Pillow`) or manually place images in '{args.input}'.")
            exit()
        except Exception as e:
            print(f"Error creating dummy images: {e}")
            exit()
    # --- End Dummy Image Creation ---

    resize_images(args.input, args.output, args.max_dim, args.force)