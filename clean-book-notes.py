#!/usr/bin/env python3

import re
import time
import yaml
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class BookNote:
    """Represents a book note with its metadata and file path."""
    
    filepath: Path
    title: Optional[str] = None
    subtitle: Optional[str] = None
    author: List[str] = field(default_factory=list)
    category: List[str] = field(default_factory=list)
    publisher: Optional[str] = None
    publish: Optional[str] = None
    total: Optional[int] = None
    isbn: Optional[str] = None
    cover: Optional[str] = None
    localCover: Optional[str] = None
    created: Optional[str] = None
    status: Optional[str] = None
    reading_list: Optional[str] = None
    content: str = ""
    
    @classmethod
    def from_file(cls, filepath: Path) -> 'BookNote':
        """Parse a book note from a markdown file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        book = cls(filepath=filepath, content=content)
        
        # Extract frontmatter
        if content.startswith('---'):
            try:
                end_index = content.index('---', 3)
                frontmatter_text = content[3:end_index]
                frontmatter = yaml.safe_load(frontmatter_text)
                
                if frontmatter:
                    book.title = book._extract_value(frontmatter.get('title'))
                    book.subtitle = book._extract_value(frontmatter.get('subtitle'))
                    book.author = book._extract_list(frontmatter.get('author', []))
                    book.category = book._extract_list(frontmatter.get('category', []))
                    book.publisher = book._extract_value(frontmatter.get('publisher'))
                    book.publish = book._extract_value(frontmatter.get('publish'))
                    book.total = frontmatter.get('total')
                    book.isbn = book._extract_value(frontmatter.get('isbn'))
                    book.cover = book._extract_value(frontmatter.get('cover'))
                    book.localCover = book._extract_value(frontmatter.get('localCover'))
                    book.created = frontmatter.get('created')
                    book.status = frontmatter.get('status')
                    book.reading_list = frontmatter.get('Reading List')
            except (ValueError, yaml.YAMLError) as e:
                print(f"Error parsing frontmatter for {filepath.name}: {e}")
        
        return book
    
    @staticmethod
    def _extract_value(value: Any) -> Optional[str]:
        """Extract string value from various frontmatter formats."""
        if value is None:
            return None
        if isinstance(value, list) and len(value) > 0:
            return str(value[0])
        if isinstance(value, str):
            return value if value and value.strip() and value.strip() != "''" else None
        return str(value) if value else None
    
    @staticmethod
    def _extract_list(value: Any) -> List[str]:
        """Extract list of strings from frontmatter."""
        if isinstance(value, list):
            return [str(v).strip().strip('"').strip("'") for v in value if v]
        if isinstance(value, str) and value:
            return [value.strip().strip('"').strip("'")]
        return []
    
    def get_missing_fields(self) -> List[str]:
        """Return a list of missing or problematic fields."""
        missing = []
        
        if not self.title:
            missing.append("title")
        if not self.author:
            missing.append("author")
        if not self.isbn:
            missing.append("ISBN")
        if not self.publisher:
            missing.append("publisher")
        if not self.publish:
            missing.append("publish date")
        if not self.total:
            missing.append("page count")
        if not self.cover:
            missing.append("cover URL")
        if not self.localCover:
            missing.append("local cover path")
        else:
            # Check if local cover actually exists
            base_path = Path("/Users/armaangupta/Documents/GuppyBrain")
            local_cover_path = base_path / self.localCover
            if not local_cover_path.exists():
                missing.append("local cover file (path exists but file missing)")
        
        return missing
    
    def update_and_save(self, updates: Dict[str, Any]) -> bool:
        """Update the book note with new data and save to file."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.startswith('---'):
                return False
            
            end_index = content.index('---', 3)
            frontmatter_text = content[3:end_index]
            body = content[end_index+3:]
            
            frontmatter = yaml.safe_load(frontmatter_text) or {}
            
            # Apply updates
            for key, value in updates.items():
                if value is not None:
                    if key == 'author' and not isinstance(value, list):
                        frontmatter[key] = [f"[[{value}]]"]
                    elif key == 'category' and not isinstance(value, list):
                        frontmatter[key] = [value]
                    else:
                        frontmatter[key] = value
            
            # Reconstruct file
            new_content = "---\n"
            new_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
            new_content += "---"
            new_content += body
            
            # Save file
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True
        except Exception as e:
            print(f"Error updating {self.filepath.name}: {e}")
            return False


class BookAPIClient:
    """Client for fetching book data from Google Books and Open Library APIs."""
    
    GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
    OPEN_LIBRARY_API = "https://openlibrary.org"
    
    def __init__(self):
        self.session = requests.Session()
    
    def search_by_title_author(self, title: str, author: str = "") -> Optional[Dict]:
        """Search for a book by title and optionally author."""
        # Try Google Books first
        query = f"{title}"
        if author:
            query += f" {author}"
        
        data = self._search_google_books(query)
        if data:
            return data
        
        # Fallback to Open Library
        return self._search_open_library(title, author)
    
    def search_by_isbn(self, isbn: str) -> Optional[Dict]:
        """Search for a book by ISBN."""
        # Clean ISBN
        isbn_clean = re.sub(r'[^0-9X]', '', isbn.upper())
        
        # Try Google Books
        data = self._search_google_books(f"isbn:{isbn_clean}")
        if data:
            return data
        
        # Try Open Library
        return self._fetch_open_library_isbn(isbn_clean)
    
    def _search_google_books(self, query: str) -> Optional[Dict]:
        """Search Google Books API."""
        try:
            response = self.session.get(
                self.GOOGLE_BOOKS_API,
                params={'q': query},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if 'items' in data and len(data['items']) > 0:
                volume = data['items'][0]['volumeInfo']
                
                result = {
                    'title': volume.get('title'),
                    'subtitle': volume.get('subtitle'),
                    'authors': volume.get('authors', []),
                    'publisher': volume.get('publisher'),
                    'publishedDate': volume.get('publishedDate'),
                    'pageCount': volume.get('pageCount'),
                    'categories': volume.get('categories', []),
                    'isbn': None,
                    'coverUrl': None
                }
                
                # Extract ISBNs
                identifiers = volume.get('industryIdentifiers', [])
                isbn_10 = None
                isbn_13 = None
                for identifier in identifiers:
                    if identifier['type'] == 'ISBN_10':
                        isbn_10 = identifier['identifier']
                    elif identifier['type'] == 'ISBN_13':
                        isbn_13 = identifier['identifier']
                
                if isbn_10 and isbn_13:
                    result['isbn'] = f"{isbn_10}, {isbn_13}"
                elif isbn_13:
                    result['isbn'] = isbn_13
                elif isbn_10:
                    result['isbn'] = isbn_10
                
                # Get cover URL
                if 'imageLinks' in volume:
                    # Prefer larger images
                    if 'large' in volume['imageLinks']:
                        result['coverUrl'] = volume['imageLinks']['large']
                    elif 'medium' in volume['imageLinks']:
                        result['coverUrl'] = volume['imageLinks']['medium']
                    elif 'thumbnail' in volume['imageLinks']:
                        result['coverUrl'] = volume['imageLinks']['thumbnail'].replace('&edge=curl', '')
                
                return result
        except Exception as e:
            print(f"Google Books API error: {e}")
        
        return None
    
    def _search_open_library(self, title: str, author: str = "") -> Optional[Dict]:
        """Search Open Library API by title and author."""
        try:
            params = {'title': title}
            if author:
                params['author'] = author
            
            response = self.session.get(
                f"{self.OPEN_LIBRARY_API}/search.json",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if 'docs' in data and len(data['docs']) > 0:
                book = data['docs'][0]
                
                result = {
                    'title': book.get('title'),
                    'subtitle': book.get('subtitle'),
                    'authors': book.get('author_name', []),
                    'publisher': book.get('publisher', [None])[0] if book.get('publisher') else None,
                    'publishedDate': str(book.get('first_publish_year', '')),
                    'pageCount': book.get('number_of_pages_median'),
                    'categories': book.get('subject', [])[:3] if book.get('subject') else [],
                    'isbn': None,
                    'coverUrl': None
                }
                
                # Get ISBNs
                isbns = book.get('isbn', [])
                if isbns:
                    # Find ISBN-10 and ISBN-13
                    isbn_10 = [i for i in isbns if len(i.replace('-', '')) == 10]
                    isbn_13 = [i for i in isbns if len(i.replace('-', '')) == 13]
                    
                    if isbn_10 and isbn_13:
                        result['isbn'] = f"{isbn_10[0]}, {isbn_13[0]}"
                    elif isbn_13:
                        result['isbn'] = isbn_13[0]
                    elif isbn_10:
                        result['isbn'] = isbn_10[0]
                
                # Get cover URL
                if book.get('cover_i'):
                    result['coverUrl'] = f"https://covers.openlibrary.org/b/id/{book['cover_i']}-L.jpg"
                
                return result
        except Exception as e:
            print(f"Open Library API error: {e}")
        
        return None
    
    def _fetch_open_library_isbn(self, isbn: str) -> Optional[Dict]:
        """Fetch book data from Open Library by ISBN."""
        try:
            response = self.session.get(
                f"{self.OPEN_LIBRARY_API}/isbn/{isbn}.json",
                timeout=10
            )
            response.raise_for_status()
            
            book = response.json()
            
            result = {
                'title': book.get('title'),
                'subtitle': book.get('subtitle'),
                'authors': [],
                'publisher': None,
                'publishedDate': book.get('publish_date'),
                'pageCount': book.get('number_of_pages'),
                'categories': book.get('subjects', [])[:3] if book.get('subjects') else [],
                'isbn': isbn,
                'coverUrl': None
            }
            
            # Get authors
            if 'authors' in book:
                for author_ref in book['authors']:
                    if 'key' in author_ref:
                        try:
                            author_response = self.session.get(
                                f"{self.OPEN_LIBRARY_API}{author_ref['key']}.json",
                                timeout=5
                            )
                            author_data = author_response.json()
                            if 'name' in author_data:
                                result['authors'].append(author_data['name'])
                        except Exception:
                            pass
            
            # Get publisher
            if 'publishers' in book and book['publishers']:
                result['publisher'] = book['publishers'][0]
            
            # Get cover
            if 'covers' in book and book['covers']:
                result['coverUrl'] = f"https://covers.openlibrary.org/b/id/{book['covers'][0]}-L.jpg"
            
            return result
        except Exception as e:
            print(f"Open Library ISBN API error: {e}")
        
        return None
    
    def download_cover(self, url: str, save_path: Path) -> bool:
        """Download a book cover image."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save image
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
        except Exception as e:
            print(f"Error downloading cover: {e}")
            return False


class BookNotesCleaner:
    """Main class for cleaning book notes."""
    
    def __init__(self, books_dir: str, covers_dir: str):
        self.books_dir = Path(books_dir)
        self.covers_dir = Path(covers_dir)
        self.api_client = BookAPIClient()
    
    def run(self):
        """Main execution method."""
        print("Book Notes Cleaner")
        print("=" * 50)
        print(f"Scanning directory: {self.books_dir}")
        print()
        
        # Get all markdown files (excluding folders)
        md_files = [f for f in self.books_dir.glob("*.md") if f.is_file()]
        
        print(f"Found {len(md_files)} book notes")
        print("=" * 50)
        print()
        
        for i, filepath in enumerate(md_files, 1):
            print(f"[{i}/{len(md_files)}] Processing: {filepath.name}")
            
            # Parse book note
            book = BookNote.from_file(filepath)
            
            # Check for missing fields
            missing = book.get_missing_fields()
            
            if not missing:
                print(f"   All fields complete")
                print()
                continue
            
            # Display missing fields
            print(f"  Title: {book.title or 'MISSING'}")
            print("  Missing fields:")
            for missing_field in missing:
                print(f"    - {missing_field}")
            
            # Ask user if they want to fix
            response = input("\n  Should I begin fixing this? (y/n/skip): ").strip().lower()
            
            if response == 'skip':
                print("  Skipping remaining books...")
                break
            elif response != 'y':
                print("  Skipping this book...")
                print()
                continue
            
            # Try to fetch missing data
            print("  Fetching data from APIs...")
            
            api_data = None
            
            # Try ISBN first if available
            if book.isbn:
                api_data = self.api_client.search_by_isbn(book.isbn)
            
            # Fallback to title/author search
            if not api_data and book.title:
                author = book.author[0] if book.author else ""
                # Clean author name (remove [[ ]] brackets)
                author = author.replace('[[', '').replace(']]', '')
                api_data = self.api_client.search_by_title_author(book.title, author)
            
            if not api_data:
                print("   Could not fetch data from APIs")
                print()
                continue
            
            # Prepare updates
            updates = {}
            
            if not book.title and api_data.get('title'):
                updates['title'] = api_data['title']
            
            if not book.subtitle and api_data.get('subtitle'):
                updates['subtitle'] = api_data['subtitle']
            
            if not book.author and api_data.get('authors'):
                # Format authors with [[ ]] for Obsidian links
                updates['author'] = [f"[[{author}]]" for author in api_data['authors']]
            
            if not book.publisher and api_data.get('publisher'):
                updates['publisher'] = api_data['publisher']
            
            if not book.publish and api_data.get('publishedDate'):
                updates['publish'] = api_data['publishedDate']
            
            if not book.total and api_data.get('pageCount'):
                updates['total'] = api_data['pageCount']
            
            if not book.isbn and api_data.get('isbn'):
                updates['isbn'] = api_data['isbn']
            
            if not book.cover and api_data.get('coverUrl'):
                updates['cover'] = api_data['coverUrl']
            
            if not book.category and api_data.get('categories'):
                updates['category'] = api_data['categories']
            
            # Handle local cover
            if api_data.get('coverUrl'):
                # Generate local cover filename
                title_clean = re.sub(r'[^\w\s-]', '', book.title or api_data.get('title', 'Unknown'))
                author_clean = ""
                if api_data.get('authors'):
                    author_clean = re.sub(r'[^\w\s-]', '', api_data['authors'][0])
                elif book.author:
                    author_clean = re.sub(r'[^\w\s-]', '', book.author[0].replace('[[', '').replace(']]', ''))
                
                date_clean = api_data.get('publishedDate', '')
                
                if author_clean and date_clean:
                    cover_filename = f"{author_clean} - {title_clean} - {date_clean}.jpg"
                elif author_clean:
                    cover_filename = f"{author_clean} - {title_clean}.jpg"
                else:
                    cover_filename = f"{title_clean}.jpg"
                
                local_cover_path = self.covers_dir / cover_filename
                relative_cover_path = f"References/Attachments/Book Search Covers/{cover_filename}"
                
                # Check if we need to download the cover
                if not local_cover_path.exists():
                    print("  Downloading cover image...")
                    if self.api_client.download_cover(api_data['coverUrl'], local_cover_path):
                        updates['localCover'] = relative_cover_path
                        print(f"   Cover downloaded: {cover_filename}")
                    else:
                        print(f"   Failed to download cover")
                else:
                    updates['localCover'] = relative_cover_path
                    print(f"   Cover already exists: {cover_filename}")
            
            # Apply updates
            if updates:
                print(f"  Updating book note with {len(updates)} fields...")
                if book.update_and_save(updates):
                    print("   Book note updated successfully")
                else:
                    print("   Failed to update book note")
            else:
                print("  No updates needed")
            
            print()
            
            # Small delay to avoid hitting API rate limits
            time.sleep(0.5)
        
        print("=" * 50)
        print("Cleaning complete!")


def main():
    books_dir = "/Users/armaangupta/Documents/GuppyBrain/References/Books"
    covers_dir = "/Users/armaangupta/Documents/GuppyBrain/References/Attachments/Book Search Covers"
    
    cleaner = BookNotesCleaner(books_dir, covers_dir)
    cleaner.run()


if __name__ == "__main__":
    main()