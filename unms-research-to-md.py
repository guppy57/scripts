#!/usr/bin/env python3
"""
Script to convert notes/annotations/comments from SQLite database to Markdown files for Obsidian vault.
"""

import sqlite3
import os
import re
import json
from pathlib import Path
import shutil
from datetime import datetime

# Configuration
OBSIDIAN_VAULT_PATH = Path("/Users/guppy57/GuppyBrain")  # Adjust this path to your actual vault location
SQLITE_DB_PATH = "/Users/guppy57/Library/Application Support/research.un.ms/data.db"  # Set this to your SQLite database path

def get_items_from_db():
    """Retrieve all items from the database."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    query = """
    SELECT i.id, i.title, i.year, i.type, c.name as category
    FROM items i
    LEFT JOIN categories c ON i.category_id = c.id
    ORDER BY i.created_at DESC
    """
    
    cursor.execute(query)
    items = cursor.fetchall()
    conn.close()
    
    return items

def display_items_in_columns(items):
    """Display items in 3 columns with numbers."""
    if not items:
        print("No items found in the database.")
        return
    
    # Calculate terminal width and column width
    terminal_width = shutil.get_terminal_size().columns
    col_width = terminal_width // 3
    
    print("\nAvailable Items:")
    print("=" * terminal_width)
    
    # Group items into rows of 3
    for i in range(0, len(items), 3):
        row_items = items[i:i+3]
        
        # Format each column
        col1 = f"{i+1}. {row_items[0][1][:col_width-10] if len(row_items[0][1]) > col_width-10 else row_items[0][1]}" if len(row_items) > 0 else ""
        col2 = f"{i+2}. {row_items[1][1][:col_width-10] if len(row_items[1][1]) > col_width-10 else row_items[1][1]}" if len(row_items) > 1 else ""
        col3 = f"{i+3}. {row_items[2][1][:col_width-10] if len(row_items[2][1]) > col_width-10 else row_items[2][1]}" if len(row_items) > 2 else ""
        
        print(f"{col1:<{col_width}} {col2:<{col_width}} {col3:<{col_width}}")
    
    print("=" * terminal_width)

def get_user_selection(max_items):
    """Get and validate user input for item selection."""
    while True:
        try:
            choice = input(f"\nEnter item number (1-{max_items}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
                
            choice_num = int(choice)
            if 1 <= choice_num <= max_items:
                return choice_num - 1  # Convert to 0-based index
            else:
                print(f"Please enter a number between 1 and {max_items}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")

def main():
    """Main function to convert SQLite notes to Markdown files."""
    print(f"Obsidian Vault Path: {OBSIDIAN_VAULT_PATH}")
    print(f"SQLite Database Path: {SQLITE_DB_PATH}")
    
    # Get all items from database
    items = get_items_from_db()
    
    if not items:
        print("No items found in the database.")
        return
    
    # Display items in columns
    display_items_in_columns(items)
    
    # Get user selection
    selection = get_user_selection(len(items))
    
    if selection is None:
        print("Goodbye!")
        return
    
    selected_item = items[selection]
    print(f"\nSelected: {selected_item[1]}")
    
    # Generate markdown file for selected item
    generate_markdown_file(selected_item[0])  # Pass item ID
    
def html_to_markdown(html_content):
    """Simple HTML to markdown converter."""
    if not html_content:
        return ""
    
    # Remove HTML tags and convert basic formatting
    text = html_content
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text)
    text = re.sub(r'<[^>]+>', '', text)  # Remove remaining HTML tags
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Clean up multiple newlines
    
    return text.strip()

def extract_page_number(position_json):
    """Extract page number from annotation position JSON."""
    if not position_json:
        return None
    
    try:
        position_data = json.loads(position_json)
        if isinstance(position_data, dict):
            # Check boundingRect first
            if 'boundingRect' in position_data and 'pageNumber' in position_data['boundingRect']:
                return position_data['boundingRect']['pageNumber']
            # Check rects array as fallback
            elif 'rects' in position_data and position_data['rects'] and len(position_data['rects']) > 0:
                if 'pageNumber' in position_data['rects'][0]:
                    return position_data['rects'][0]['pageNumber']
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    
    return None


def sanitize_filename(filename):
    """Sanitize filename for file system."""
    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip()
    return filename[:100]  # Limit length

def get_item_details(item_id):
    """Get full details for a specific item including annotations and comments."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    # Get item details
    item_query = """
    SELECT i.*, c.name as category_name
    FROM items i
    LEFT JOIN categories c ON i.category_id = c.id
    WHERE i.id = ?
    """
    cursor.execute(item_query, (item_id,))
    item = cursor.fetchone()
    
    # Get authors
    authors_query = """
    SELECT a.first_name, a.last_name
    FROM authors a
    JOIN items_authors ia ON a.id = ia.author_id
    WHERE ia.item_id = ?
    """
    cursor.execute(authors_query, (item_id,))
    authors = cursor.fetchall()
    
    # Get annotations
    annotations_query = """
    SELECT id, type, comment, content, position, created_at
    FROM annotations
    WHERE item_id = ?
    ORDER BY created_at ASC
    """
    cursor.execute(annotations_query, (item_id,))
    annotations = cursor.fetchall()
    
    # Get general notes for the item
    notes_query = """
    SELECT content, created_at
    FROM notes
    WHERE item_id = ?
    ORDER BY created_at ASC
    """
    cursor.execute(notes_query, (item_id,))
    notes = cursor.fetchall()
    
    conn.close()
    
    return {
        'item': item,
        'authors': authors,
        'annotations': annotations,
        'notes': notes
    }

def generate_markdown_file(item_id):
    """Generate a markdown file for the selected item."""
    data = get_item_details(item_id)
    item = data['item']
    
    if not item:
        print("Item not found!")
        return
    
    # Create filename
    title = item[4] if item[4] else f"Item_{item[0]}"
    filename = sanitize_filename(title) + ".md"
    filepath = OBSIDIAN_VAULT_PATH / filename
    
    # Ensure directory exists
    OBSIDIAN_VAULT_PATH.mkdir(parents=True, exist_ok=True)
    
    # Generate markdown content
    markdown_content = []
    
    # YAML frontmatter - include all item properties
    markdown_content.append("---")
    markdown_content.append(f'title: "{title}"')
    markdown_content.append(f"year: {item[1] if item[1] else ''}")
    markdown_content.append(f"type: {item[2] if item[2] else ''}")
    markdown_content.append(f"date: {item[5] if item[5] else ''}")
    markdown_content.append(f"link: {item[6] if item[6] else ''}")
    markdown_content.append(f"doi: {item[7] if item[7] else ''}")
    markdown_content.append(f"isbn: {item[8] if item[8] else ''}")
    markdown_content.append(f"abstract: {item[9] if item[9] else ''}")
    markdown_content.append(f"ai_summary: {item[10] if item[10] else ''}")
    markdown_content.append(f"publisher: {item[11] if item[11] else ''}")
    markdown_content.append(f"catalogue: {item[12] if item[12] else ''}")
    markdown_content.append(f"issue: {item[13] if item[13] else ''}")
    markdown_content.append(f"pages: {item[14] if item[14] else ''}")
    markdown_content.append(f"keywords: {item[15] if item[15] else ''}")
    markdown_content.append(f"series: {item[16] if item[16] else ''}")
    markdown_content.append(f"category: {data['item'][-1] if data['item'][-1] else ''}")
    markdown_content.append(f"created_at: {item[20] if item[20] else ''}")

    # Authors as YAML list
    markdown_content.append("authors:")
    if data['authors']:
        for author in data['authors']:
            author_name = f"{author[0]} {author[1]}" if author[0] and author[1] else (author[0] or author[1] or 'Unknown')
            markdown_content.append(f'- "[[{author_name}]]"')
    
    markdown_content.append("---")
    markdown_content.append("")
    
    # Notes
    if data['notes']:
        markdown_content.append("## Notes")
        for note in data['notes']:
            if note[0] and note[0].strip() not in ['<p><br></p>', '<p></p>', '']:
                content = html_to_markdown(note[0])
                if content:
                    markdown_content.append(content)
                    markdown_content.append("")
    
    # Annotations with their comments
    if data['annotations']:
        markdown_content.append("## Annotations")
        
        # Open database connection for comment queries
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        for annotation in data['annotations']:
            try:
                # annotation structure: [id, type, comment, content, position, created_at]
                annotation_id = annotation[0]
                content_json = json.loads(annotation[3]) if annotation[3] else {}
                position_json = annotation[4] if annotation[4] else None
                text = content_json.get('text', '') if content_json else ''
                
                if text:
                    # Extract page number from position
                    page_number = extract_page_number(position_json)
                    
                    # Create the annotation with page number
                    if page_number:
                        markdown_content.append(f'> "{text}" (p.{page_number})')
                    else:
                        markdown_content.append(f'> "{text}"')
                    
                    markdown_content.append("")
                    
                    # Get comments for this specific annotation
                    comments_query = """
                    SELECT content, is_ai, created_at
                    FROM comments
                    WHERE annotation_id = ?
                    ORDER BY created_at ASC
                    """
                    cursor.execute(comments_query, (annotation_id,))
                    annotation_comments = cursor.fetchall()
                    
                    # Add comments under this annotation
                    for comment in annotation_comments:
                        if comment[0]:  # content
                            try:
                                content_json = json.loads(comment[0]) if comment[0] else {}
                                if isinstance(content_json, dict):
                                    comment_text = content_json.get('text', str(content_json))
                                else:
                                    comment_text = str(content_json)
                                
                                if comment_text:
                                    converted_text = html_to_markdown(comment_text)
                                    if converted_text:
                                        ai_marker = " (AI)" if comment[1] else ""
                                        markdown_content.append(f"{converted_text}{ai_marker}")
                                        markdown_content.append("")
                            except json.JSONDecodeError:
                                comment_text = html_to_markdown(str(comment[0]))
                                if comment_text:
                                    ai_marker = " (AI)" if comment[1] else ""
                                    markdown_content.append(f"{comment_text}{ai_marker}")
                                    markdown_content.append("")
                    
            except (json.JSONDecodeError, IndexError):
                continue
        
        conn.close()
    
    # Write to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(markdown_content))
    
    print(f"\nMarkdown file created: {filepath}")
    print(f"File saved to: {filepath.absolute()}")

if __name__ == "__main__":
    main()