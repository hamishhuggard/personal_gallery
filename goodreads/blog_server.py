import os
import glob
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from markdown import markdown

REVIEWS_DIR = os.path.join(os.path.dirname(__file__), 'reviews')

app = FastAPI(title="Goodreads Review Blog")

# Helper to parse a markdown file with YAML front matter
def parse_review_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            front_matter = yaml.safe_load(parts[1])
            markdown_content = parts[2].strip()
            return front_matter, markdown_content
    return None, content

# Helper to get all reviews
def get_all_reviews():
    reviews = []
    for path in glob.glob(os.path.join(REVIEWS_DIR, '*.md')):
        front, _ = parse_review_file(path)
        if front and 'title' in front:
            slug = os.path.splitext(os.path.basename(path))[0]
            title = front.get('title', 'Untitled')
            # Ensure title is a string
            if not isinstance(title, str):
                title = str(title)
            reviews.append({
                'title': title,
                'author': front.get('author', 'Unknown'),
                'slug': slug
            })
    # Sort by title (as string)
    reviews.sort(key=lambda r: r['title'].lower())
    return reviews

@app.get('/', response_class=HTMLResponse)
def index():
    reviews = get_all_reviews()
    html = "<h1>Goodreads Review Blog</h1><ul>"
    for r in reviews:
        html += f'<li><a href="/review/{r["slug"]}">{r["title"]}</a> by {r["author"]}</li>'
    html += "</ul>"
    return html

@app.get('/review/{slug}', response_class=HTMLResponse)
def review(slug: str):
    filepath = os.path.join(REVIEWS_DIR, f'{slug}.md')
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Review not found")
    front, md_content = parse_review_file(filepath)
    if not front:
        raise HTTPException(status_code=500, detail="Invalid review file")
    html = f"<h1>{front.get('title', 'Untitled')}</h1>"
    html += f"<h3>by {front.get('author', 'Unknown')}</h3>"
    html += f"<div>{markdown(md_content)}</div>"
    html += '<p><a href="/">Back to all reviews</a></p>'
    return html 