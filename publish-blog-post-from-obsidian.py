#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian to MDX Blog Post Converter
Converts Obsidian markdown posts to MDX format for blog deployment
"""

import os
import re
import shutil
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configuration
OBSIDIAN_BLOG_DIR = "/Users/guppy57/GuppyBrain/Manuscripts/Personal Blog"
OBSIDIAN_ATTACHMENTS_DIR = "/Users/guppy57/GuppyBrain/References/Attachments"
BLOG_REPO_DIR = "/Users/guppy57/GitHub/guppy.land"
BLOG_POSTS_DIR = os.path.join(BLOG_REPO_DIR, "data", "posts")
PUBLIC_IMAGES_DIR = os.path.join(BLOG_REPO_DIR, "public", "images", "articles")
AUTHOR = "Armaan Gupta"


def list_blog_posts() -> List[Tuple[str, str]]:
    """
    List all markdown files in the Obsidian blog directory
    Returns list of tuples (filename, full_path)
    """
    posts = []
    
    if not os.path.exists(OBSIDIAN_BLOG_DIR):
        print(f"Error: Obsidian blog directory not found: {OBSIDIAN_BLOG_DIR}")
        return posts
    
    for file in os.listdir(OBSIDIAN_BLOG_DIR):
        if file.endswith('.md'):
            full_path = os.path.join(OBSIDIAN_BLOG_DIR, file)
            posts.append((file, full_path))
    
    return sorted(posts)


def select_post(posts: List[Tuple[str, str]]) -> Optional[str]:
    """
    Display numbered list of posts and get user selection
    Returns the selected post path or None
    """
    if not posts:
        print("No blog posts found in the Obsidian vault.")
        return None
    
    print("\nAvailable Blog Posts:")
    print("-" * 50)
    
    for i, (filename, _) in enumerate(posts, 1):
        # Remove .md extension for display
        display_name = filename[:-3]
        print(f"{i:3}. {display_name}")
    
    print("-" * 50)
    
    while True:
        try:
            choice = input("\nEnter the number of the post to convert (or 'q' to quit): ")
            
            if choice.lower() == 'q':
                print("Exiting...")
                return None
            
            index = int(choice) - 1
            if 0 <= index < len(posts):
                return posts[index][1]
            else:
                print(f"Please enter a number between 1 and {len(posts)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")


def parse_obsidian_post(file_path: str) -> Tuple[Dict, str]:
    """
    Parse Obsidian markdown file to extract frontmatter and content
    Returns tuple of (frontmatter_dict, content_string)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract frontmatter
    frontmatter = {}
    draft_content = ""
    
    # Check if file starts with frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1])
            except yaml.YAMLError as e:
                print(f"Warning: Error parsing YAML frontmatter: {e}")
                frontmatter = {}
            
            main_content = parts[2]
        else:
            main_content = content
    else:
        main_content = content
    
    # Extract content under ## Draft heading
    if "## Draft" in main_content:
        parts = main_content.split("## Draft", 1)
        if len(parts) > 1:
            draft_content = parts[1].strip()
        else:
            draft_content = main_content.strip()
    else:
        # If no Draft section found, use the entire content after frontmatter
        print("Warning: No '## Draft' section found. Using entire content.")
        draft_content = main_content.strip()
    
    return frontmatter, draft_content


def convert_frontmatter(obsidian_fm: Dict) -> Dict:
    """
    Convert Obsidian frontmatter to MDX frontmatter format
    Maps bp_ prefixed fields to MDX fields
    """
    mdx_fm = {}
    
    # Map Obsidian fields to MDX fields
    field_mapping = {
        'bp_title': 'title',
        'bp_description': 'description',
        'bp_slug': 'slug',
        'bp_publishingDate': 'publishingDate',
        'bp_keywords': 'tags',
        'bp_categories': 'categories',
        'bp_coverImage': 'featuredImage'
    }
    
    for obsidian_key, mdx_key in field_mapping.items():
        if obsidian_key in obsidian_fm:
            value = obsidian_fm[obsidian_key]
            
            # Ensure categories is always a list
            if mdx_key == 'categories':
                if isinstance(value, str):
                    mdx_fm[mdx_key] = [value]
                elif isinstance(value, list):
                    mdx_fm[mdx_key] = value
                else:
                    mdx_fm[mdx_key] = []
            else:
                mdx_fm[mdx_key] = value
    
    # Add fixed author field
    mdx_fm['author'] = AUTHOR
    
    # If no publishingDate, use today's date
    if 'publishingDate' not in mdx_fm:
        mdx_fm['publishingDate'] = datetime.now().strftime('%Y-%m-%d')
    
    return mdx_fm


def process_content(content: str, slug: str, obsidian_vault_path: str) -> Tuple[str, List[str]]:
    """
    Process Obsidian content for MDX compatibility
    Returns tuple of (processed_content, list_of_attachment_paths)
    """
    processed = content
    attachments = []
    
    # Remove Obsidian [[wiki links]] syntax
    processed = re.sub(r'\[\[([^\]]+)\]\]', r'\1', processed)
    
    # Find and process math equations (wrap standalone equations)
    # Match equations that are on their own line
    math_pattern = r'^(\$[^\$\n]+\$)\s*$'
    processed = re.sub(
        math_pattern,
        r'<div className="text-center">\n\n\1\n\n</div>',
        processed,
        flags=re.MULTILINE
    )
    
    # Find all image references in various formats
    
    # Obsidian format: ![[filename.png]]
    obsidian_img_pattern = r'!\[\[([^\]]+\.(png|jpg|jpeg|gif|svg|webp))\]\]'
    
    for match in re.finditer(obsidian_img_pattern, processed, re.IGNORECASE):
        img_name = match.group(1)
        attachments.append(img_name)
        # Replace with HTML img tag
        new_path = f'/images/articles/{slug}/{img_name}'
        processed = processed.replace(match.group(0), f'<img src="{new_path}" alt="{img_name}" className="w-full h-auto" />')
    
    # Simple Obsidian format: !filename.png (no brackets, allows spaces in filename)
    simple_img_pattern = r'^!([^\[\n]+\.(png|jpg|jpeg|gif|svg|webp))$'
    
    for match in re.finditer(simple_img_pattern, processed, re.IGNORECASE | re.MULTILINE):
        img_name = match.group(1)
        attachments.append(img_name)
        # Replace with HTML img tag
        new_path = f'/images/articles/{slug}/{img_name}'
        processed = processed.replace(match.group(0), f'<img src="{new_path}" alt="{img_name}" className="w-full h-auto" />')
    
    # Standard markdown images: ![alt](path)
    std_img_pattern = r'!\[([^\]]*)\]\(([^)]+\.(png|jpg|jpeg|gif|svg|webp))\)'
    
    for match in re.finditer(std_img_pattern, processed, re.IGNORECASE):
        img_path = match.group(2)
        # If it's not already pointing to the blog repo, add it to attachments
        if not img_path.startswith('/images/articles/'):
            img_name = os.path.basename(img_path)
            attachments.append(img_name)
            new_path = f'/images/articles/{slug}/{img_name}'
            processed = processed.replace(
                match.group(0),
                f'<img src="{new_path}" alt="{match.group(1)}" className="w-full h-auto" />'
            )
    
    return processed, attachments


def find_attachment_in_vault(attachment_name: str, vault_base: str = None) -> Optional[str]:
    """
    Find an attachment file in the Obsidian vault
    Searches the dedicated attachments directory
    """
    # Look in the dedicated Obsidian attachments directory
    attachment_path = os.path.join(OBSIDIAN_ATTACHMENTS_DIR, attachment_name)
    
    if os.path.exists(attachment_path):
        return attachment_path
    
    # If not found, return None
    return None


def copy_attachments(attachments: List[str], slug: str, obsidian_post_path: str) -> List[str]:
    """
    Copy attachments from Obsidian vault to blog repo
    Returns list of successfully copied attachments
    """
    if not attachments:
        return []
    
    # Create target directory
    target_dir = os.path.join(PUBLIC_IMAGES_DIR, slug)
    os.makedirs(target_dir, exist_ok=True)
    
    copied = []
    
    for attachment in attachments:
        # Find the attachment in the vault
        source_path = find_attachment_in_vault(attachment)
        
        if source_path and os.path.exists(source_path):
            target_path = os.path.join(target_dir, attachment)
            try:
                shutil.copy2(source_path, target_path)
                copied.append(attachment)
                print(f"  [OK] Copied: {attachment}")
            except Exception as e:
                print(f"  [ERROR] Failed copying {attachment}: {e}")
        else:
            print(f"  [WARNING] Attachment not found: {attachment}")
    
    return copied


def write_mdx_file(frontmatter: Dict, content: str, slug: str) -> str:
    """
    Write the MDX file to the blog repository
    Returns the path of the created file
    """
    # Ensure the posts directory exists
    os.makedirs(BLOG_POSTS_DIR, exist_ok=True)
    
    # Create MDX filename
    mdx_filename = f"{slug}.mdx"
    mdx_path = os.path.join(BLOG_POSTS_DIR, mdx_filename)
    
    # Format frontmatter as YAML
    fm_lines = ["---"]
    
    # Maintain order for readability
    key_order = ['title', 'description', 'slug', 'publishingDate', 'author', 'tags', 'categories', 'featuredImage']
    
    for key in key_order:
        if key in frontmatter:
            value = frontmatter[key]
            if isinstance(value, list):
                fm_lines.append(f"{key}:")
                for item in value:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{key}: {value}")
    
    # Add any other keys that weren't in the standard order
    for key, value in frontmatter.items():
        if key not in key_order:
            if isinstance(value, list):
                fm_lines.append(f"{key}:")
                for item in value:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{key}: {value}")
    
    fm_lines.append("---")
    
    # Combine frontmatter and content
    mdx_content = "\n".join(fm_lines) + "\n" + content
    
    # Write to file
    with open(mdx_path, 'w', encoding='utf-8') as f:
        f.write(mdx_content)
    
    return mdx_path


def main():
    """Main execution function"""
    print("\n===== Obsidian to MDX Blog Post Converter =====")
    print("=" * 50)
    
    # List available posts
    posts = list_blog_posts()
    
    # Get user selection
    selected_post = select_post(posts)
    if not selected_post:
        return
    
    post_name = os.path.basename(selected_post)[:-3]
    print(f"\nConverting: {post_name}")
    print("-" * 50)
    
    # Parse the Obsidian post
    print("1. Parsing Obsidian post...")
    obsidian_fm, draft_content = parse_obsidian_post(selected_post)
    
    # Convert frontmatter
    print("2. Converting frontmatter...")
    mdx_fm = convert_frontmatter(obsidian_fm)
    
    # Get slug for file naming
    slug = mdx_fm.get('slug', post_name.lower().replace(' ', '-'))
    
    # Process content
    print("3. Processing content for MDX...")
    processed_content, attachments = process_content(draft_content, slug, selected_post)
    
    # Copy attachments if any
    if attachments:
        print(f"4. Copying {len(attachments)} attachment(s)...")
        copied = copy_attachments(attachments, slug, selected_post)
        if copied:
            print(f"   Successfully copied {len(copied)} file(s)")
    else:
        print("4. No attachments to copy")
    
    # Write MDX file
    print("5. Writing MDX file...")
    mdx_path = write_mdx_file(mdx_fm, processed_content, slug)
    
    # Success message
    print("\n" + "=" * 50)
    print("SUCCESS! Conversion Complete")
    print(f"MDX file created: {mdx_path}")
    if attachments:
        print(f"Images directory: {os.path.join(PUBLIC_IMAGES_DIR, slug)}")
    print("\nYour blog post is ready for deployment!")


if __name__ == "__main__":
    main()