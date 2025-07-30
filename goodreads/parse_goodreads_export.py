import pandas as pd
import os
import re
import argparse
from html2text import html2text

def create_review_files(csv_file_path, output_directory="./reviews"):
    """
    Reads a CSV file, extracts rows with non-empty "My Review" content,
    converts HTML reviews to markdown, and creates individual Markdown files with YAML front matter.

    Args:
        csv_file_path (str): The path to the input CSV file.
        output_directory (str): The directory where review files will be saved.
                                 Defaults to "./reviews".
    """
    try:
        df = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print(f"Error: CSV file not found at '{csv_file_path}'")
        return

    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Process all rows and filter out empty reviews after HTML conversion
    files_created = 0
    
    for index, row in df.iterrows():
        # Skip if review is NaN
        if pd.isna(row['My Review']):
            continue
        # Get the review content and convert HTML to markdown
        review_content = str(row['My Review']).strip()
        
        # Skip if review is empty after stripping
        if not review_content:
            continue
            
        # Convert HTML to markdown
        markdown_content = html2text(review_content)
        
        # Skip if markdown content is empty after conversion
        if not markdown_content.strip():
            continue
        
        # Sanitize title for filename
        title_for_filename = re.sub(r'[^\w\s-]', '', str(row['Title'])).strip()
        title_for_filename = re.sub(r'[-\s]+', '-', title_for_filename).lower()
        if not title_for_filename: # Fallback if title becomes empty after sanitization
            title_for_filename = f"book-id-{row['Book Id']}"

        # Construct filename, adding author if available and making sure it's unique
        author_for_filename = re.sub(r'[^\w\s-]', '', str(row['Author'])).strip()
        author_for_filename = re.sub(r'[-\s]+', '-', author_for_filename).lower()
        if author_for_filename:
            filename = os.path.join(output_directory, f"{title_for_filename}-{author_for_filename}.md")
        else:
            filename = os.path.join(output_directory, f"{title_for_filename}.md")

        # Handle potential duplicate filenames
        counter = 1
        original_filename = filename # Keep original for comparison, though not strictly needed here
        while os.path.exists(filename):
            if author_for_filename:
                filename = os.path.join(output_directory, f"{title_for_filename}-{author_for_filename}-{counter}.md")
            else:
                filename = os.path.join(output_directory, f"{title_for_filename}-{counter}.md")
            counter += 1

        # Prepare YAML front matter
        front_matter = {
            "title": row['Title'],
            "author": row['Author'],
            "average_rating": row['Average Rating'],
            "my_rating": row['My Rating'],
            "isbn": row['ISBN'],
            "isbn13": row['ISBN13'],
            "publisher": row['Publisher'],
            "year_published": row['Year Published'],
            "original_publication_year": row['Original Publication Year'],
            "date_read": row['Date Read'],
            "date_added": row['Date Added'],
            "bookshelves": row['Bookshelves'],
            "exclusive_shelf": row['Exclusive Shelf'],
            "read_count": row['Read Count'],
            "owned_copies": row['Owned Copies']
        }

        # Convert front matter to YAML string format
        yaml_string = "---\n"
        for key, value in front_matter.items():
            # Handle NaN values for proper YAML output
            if pd.isna(value):
                yaml_string += f"{key}: \n"
            else:
                # Basic escaping for strings that might contain colons or special chars
                # Corrected line: Use .format() or concatenation for the escaped quote
                if isinstance(value, str) and (':' in value or '#' in value or '[' in value or '{' in value or '!' in value or '"' in value):
                    # Escape internal double quotes by replacing " with \"
                    escaped_value = str(value).replace('"', '\\"')
                    yaml_string += f'{key}: "{escaped_value}"\n' # Use single quotes for the f-string's outer literal
                else:
                    yaml_string += f"{key}: {value}\n"
        yaml_string += "---\n\n"

        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(yaml_string)
            f.write(markdown_content)

        files_created += 1
        print(f"Created review file: {filename}")

    if files_created == 0:
        print("No reviews found with non-empty content after HTML conversion.")
    else:
        print(f"\nTotal files created: {files_created}")

def main():
    parser = argparse.ArgumentParser(description='Extract Goodreads reviews from CSV and convert to markdown files')
    parser.add_argument('-i', '--input', help='Path to the Goodreads CSV export file')
    parser.add_argument('-o', '--output', default='./reviews', 
                       help='Output directory for review files (default: ./reviews)')
    
    args = parser.parse_args()
    
    create_review_files(args.input, args.output)

if __name__ == "__main__":
    main()
