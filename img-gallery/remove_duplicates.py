#!/usr/bin/env python3
"""
Remove duplicate images from a directory and all subdirectories.
Uses perceptual hashing to detect duplicates, even if they have different names or slight variations.

Usage:
    python remove_duplicates.py /path/to/images
    python remove_duplicates.py /path/to/images --dry-run
    python remove_duplicates.py /path/to/images --keep-oldest
"""

import argparse
import os
import sys
from pathlib import Path
from collections import defaultdict
import hashlib
from PIL import Image
import imagehash
from typing import Dict, List, Tuple, Set
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_image_hash(image_path: Path) -> str:
    """
    Generate a perceptual hash for an image.
    Returns None if the image cannot be processed.
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Generate perceptual hash
            return str(imagehash.average_hash(img))
    except Exception as e:
        logger.warning(f"Could not process {image_path}: {e}")
        return None

def get_file_hash(image_path: Path) -> str:
    """
    Generate a SHA256 hash of the file content.
    """
    try:
        with open(image_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Could not hash {image_path}: {e}")
        return None

def find_images(directory: Path) -> List[Path]:
    """
    Find all image files in the directory and subdirectories.
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.tif'}
    images = []
    
    for ext in image_extensions:
        images.extend(directory.rglob(f'*{ext}'))
        images.extend(directory.rglob(f'*{ext.upper()}'))
    
    return sorted(images)

def find_duplicates(directory: Path, use_perceptual_hash: bool = True) -> Dict[str, List[Path]]:
    """
    Find duplicate images in the directory.
    Returns a dictionary mapping hash to list of file paths.
    """
    images = find_images(directory)
    logger.info(f"Found {len(images)} images to analyze")
    
    hash_groups = defaultdict(list)
    
    for i, image_path in enumerate(images, 1):
        if i % 100 == 0:
            logger.info(f"Processed {i}/{len(images)} images...")
        
        if use_perceptual_hash:
            image_hash = get_image_hash(image_path)
        else:
            image_hash = get_file_hash(image_path)
        
        if image_hash:
            hash_groups[image_hash].append(image_path)
    
    # Filter out groups with only one image (no duplicates)
    duplicates = {hash_val: paths for hash_val, paths in hash_groups.items() if len(paths) > 1}
    
    return duplicates

def remove_duplicates(duplicates: Dict[str, List[Path]], keep_oldest: bool = True, dry_run: bool = False) -> Tuple[int, int]:
    """
    Remove duplicate images, keeping one from each group.
    
    Args:
        duplicates: Dictionary mapping hash to list of file paths
        keep_oldest: If True, keep the oldest file; if False, keep the newest
        dry_run: If True, don't actually delete files, just show what would be deleted
    
    Returns:
        Tuple of (files_kept, files_removed)
    """
    files_kept = 0
    files_removed = 0
    
    for hash_val, file_paths in duplicates.items():
        # Sort by modification time
        file_paths.sort(key=lambda p: p.stat().st_mtime, reverse=not keep_oldest)
        
        # Keep the first one (oldest if keep_oldest=True, newest if keep_oldest=False)
        keep_path = file_paths[0]
        remove_paths = file_paths[1:]
        
        logger.info(f"\nDuplicate group (hash: {hash_val[:8]}...):")
        logger.info(f"  Keeping: {keep_path}")
        files_kept += 1
        
        for remove_path in remove_paths:
            if dry_run:
                logger.info(f"  Would remove: {remove_path}")
            else:
                try:
                    remove_path.unlink()
                    logger.info(f"  Removed: {remove_path}")
                    files_removed += 1
                except Exception as e:
                    logger.error(f"  Failed to remove {remove_path}: {e}")
    
    return files_kept, files_removed

def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate images from a directory and all subdirectories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python remove_duplicates.py /path/to/images
  python remove_duplicates.py /path/to/images --dry-run
  python remove_duplicates.py /path/to/images --keep-newest
  python remove_duplicates.py /path/to/images --exact-match-only
        """
    )
    
    parser.add_argument(
        'directory',
        type=Path,
        help='Directory containing images to check for duplicates'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting files'
    )
    
    parser.add_argument(
        '--keep-newest',
        action='store_true',
        help='Keep the newest file instead of the oldest (default)'
    )
    
    parser.add_argument(
        '--exact-match-only',
        action='store_true',
        help='Only detect exact file duplicates (faster, but misses similar images)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate directory
    if not args.directory.exists():
        logger.error(f"Directory does not exist: {args.directory}")
        sys.exit(1)
    
    if not args.directory.is_dir():
        logger.error(f"Path is not a directory: {args.directory}")
        sys.exit(1)
    
    logger.info(f"Scanning directory: {args.directory}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Keep newest: {args.keep_newest}")
    logger.info(f"Exact match only: {args.exact_match_only}")
    
    # Find duplicates
    duplicates = find_duplicates(args.directory, use_perceptual_hash=not args.exact_match_only)
    
    if not duplicates:
        logger.info("No duplicates found!")
        return
    
    # Show summary
    total_duplicates = sum(len(paths) - 1 for paths in duplicates.values())
    logger.info(f"\nFound {len(duplicates)} groups of duplicates")
    logger.info(f"Total duplicate files: {total_duplicates}")
    
    # Remove duplicates
    files_kept, files_removed = remove_duplicates(
        duplicates,
        keep_oldest=not args.keep_newest,
        dry_run=args.dry_run
    )
    
    # Summary
    logger.info(f"\nSummary:")
    logger.info(f"  Files kept: {files_kept}")
    if args.dry_run:
        logger.info(f"  Files that would be removed: {files_removed}")
    else:
        logger.info(f"  Files removed: {files_removed}")

if __name__ == "__main__":
    main() 