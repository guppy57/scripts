#!/usr/bin/env python3

import re
import requests
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration - Edit these paths as needed
TEMPLATE_PATH = "/Users/armaangupta/Documents/GuppyBrain/Templates/New Book.md"
BOOKS_DIR = "/Users/armaangupta/Documents/GuppyBrain/References/Books"
COVERS_DIR = "/Users/armaangupta/Documents/GuppyBrain/References/Attachments/Book Search Covers"


class BookAPIClient:
    """Client for fetching book data from Google Books and Open Library APIs."""
    
    GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
    OPEN_LIBRARY_API = "https://openlibrary.org"
    
    def __init__(self):
        self.session = requests.Session()
    
    def search_multiple_sources(self, title: str, author: str = "") -> List[Dict]:
        """Search multiple APIs concurrently and return combined results."""
        results = []
        
        # Create search queries
        queries = [
            (self._search_google_books, f"{title} {author}".strip()),
            (self._search_open_library, title, author)
        ]
        
        # Search concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_source = {}
            
            # Submit Google Books search
            future_to_source[executor.submit(self._search_google_books, queries[0][1])] = "google"
            
            # Submit Open Library search
            future_to_source[executor.submit(self._search_open_library, queries[1][1], queries[1][2])] = "openlibrary"
            
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    result = future.result(timeout=10)
                    if result:
                        result['source'] = source
                        results.append(result)
                except Exception as e:
                    print(f"Error searching {source}: {e}")
        
        return results
    
    def search_books_by_title_author(self, title: str, author: str = "") -> List[Dict]:
        """Search for books and return up to 5 best matches."""
        print("Searching for books...")
        
        all_results = []
        
        # Try different search combinations for better results
        search_terms = [
            f"{title} {author}".strip(),
            f'intitle:"{title}" inauthor:"{author}"' if author else f'intitle:"{title}"',
            title
        ]
        
        for search_term in search_terms:
            # Google Books search
            try:
                google_results = self._search_google_books_multiple(search_term)
                all_results.extend(google_results)
            except Exception as e:
                print(f"Google Books search error: {e}")
            
            # Open Library search
            try:
                ol_result = self._search_open_library(title, author)
                if ol_result:
                    ol_result['source'] = 'openlibrary'
                    all_results.append(ol_result)
            except Exception as e:
                print(f"Open Library search error: {e}")
        
        # Deduplicate by ISBN or title+author
        seen = set()
        unique_results = []
        
        for result in all_results:
            # Create a key for deduplication
            isbn_key = result.get('isbn', '').replace(',', '').replace(' ', '')
            title_key = f"{result.get('title', '').lower().strip()}_{result.get('authors', [''])[0].lower().strip()}"
            
            key = isbn_key if isbn_key else title_key
            
            if key and key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # Sort by relevance (exact title matches first, then by publication date)
        def relevance_score(book):
            score = 0
            book_title = book.get('title', '').lower()
            search_title = title.lower()
            
            # Exact title match gets highest score
            if book_title == search_title:
                score += 100
            elif search_title in book_title or book_title in search_title:
                score += 50
            
            # Author match
            if author:
                book_authors = [a.lower() for a in book.get('authors', [])]
                if any(author.lower() in ba or ba in author.lower() for ba in book_authors):
                    score += 30
            
            # Prefer more recent publications
            pub_date = book.get('publishedDate', '')
            if pub_date:
                try:
                    year = int(re.findall(r'\d{4}', pub_date)[0])
                    score += min(year - 1900, 25)  # Cap at 25 points
                except Exception:
                    pass
            
            return score
        
        unique_results.sort(key=relevance_score, reverse=True)
        return unique_results[:5]
    
    def _search_google_books_multiple(self, query: str) -> List[Dict]:
        """Search Google Books and return multiple results."""
        try:
            response = self.session.get(
                self.GOOGLE_BOOKS_API,
                params={'q': query, 'maxResults': 20},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'items' in data:
                for item in data['items']:
                    volume = item['volumeInfo']
                    result = self._format_google_result(volume)
                    if result:
                        result['source'] = 'google'
                        results.append(result)
            
            return results
        except Exception as e:
            print(f"Google Books API error: {e}")
            return []
    
    def _search_google_books(self, query: str) -> Optional[Dict]:
        """Search Google Books API and return the best result."""
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
                return self._format_google_result(volume)
        except Exception as e:
            print(f"Google Books API error: {e}")
        
        return None
    
    def _format_google_result(self, volume: Dict) -> Optional[Dict]:
        """Format Google Books API result."""
        if not volume.get('title'):
            return None
        
        result = {
            'title': volume.get('title'),
            'subtitle': volume.get('subtitle'),
            'authors': volume.get('authors', []),
            'publisher': volume.get('publisher'),
            'publishedDate': volume.get('publishedDate'),
            'pageCount': volume.get('pageCount'),
            'categories': volume.get('categories', []),
            'description': volume.get('description', '')[:200] + '...' if volume.get('description') else '',
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
            if 'large' in volume['imageLinks']:
                result['coverUrl'] = volume['imageLinks']['large']
            elif 'medium' in volume['imageLinks']:
                result['coverUrl'] = volume['imageLinks']['medium']
            elif 'thumbnail' in volume['imageLinks']:
                result['coverUrl'] = volume['imageLinks']['thumbnail'].replace('&edge=curl', '')
        
        return result
    
    def _search_open_library(self, title: str, author: str = "") -> Optional[Dict]:
        """Search Open Library API by title and author."""
        try:
            params = {'title': title, 'limit': 1}
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
                    'description': '',
                    'isbn': None,
                    'coverUrl': None
                }
                
                # Get ISBNs
                isbns = book.get('isbn', [])
                if isbns:
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


class BookNoteCreator:
    """Creates new book notes from templates."""
    
    def __init__(self, template_path: str, books_dir: str, covers_dir: str):
        self.template_path = Path(template_path)
        self.books_dir = Path(books_dir)
        self.covers_dir = Path(covers_dir)
        self.api_client = BookAPIClient()
    
    def run(self):
        """Main execution method."""
        print("Create Book Notes")
        print("=" * 50)
        print()
        
        # Get user input
        title = input("Enter book title: ").strip()
        if not title:
            print("Title is required!")
            return
        
        author = input("Enter author name (optional): ").strip()
        print()
        
        # Search for books
        books = self.api_client.search_books_by_title_author(title, author)
        
        if not books:
            print("No books found matching your search.")
            return
        
        print(f"Found {len(books)} book(s):")
        print("=" * 50)
        
        # Display options
        for i, book in enumerate(books, 1):
            print(f"{i}. {book['title']}")
            if book.get('subtitle'):
                print(f"   Subtitle: {book['subtitle']}")
            
            authors = book.get('authors', [])
            if authors:
                print(f"   Author(s): {', '.join(authors)}")
            
            pub_info = []
            if book.get('publisher'):
                pub_info.append(book['publisher'])
            if book.get('publishedDate'):
                pub_info.append(book['publishedDate'])
            if pub_info:
                print(f"   Published: {', '.join(pub_info)}")
            
            if book.get('pageCount'):
                print(f"   Pages: {book['pageCount']}")
            
            if book.get('isbn'):
                print(f"   ISBN: {book['isbn']}")
            
            if book.get('description'):
                print(f"   Description: {book['description']}")
            
            print(f"   Source: {book.get('source', 'unknown')}")
            print()
        
        # Get user selection
        while True:
            try:
                choice = input(f"Select a book (1-{len(books)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(books):
                    selected_book = books[choice_num - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(books)}")
            except ValueError:
                print("Please enter a valid number")
        
        print()
        print(f"Creating note for: {selected_book['title']}")
        
        # Create the book note
        success = self.create_book_note(selected_book)
        
        if success:
            print(" Book note created successfully!")
        else:
            print(" Failed to create book note")
    
    def create_book_note(self, book: Dict) -> bool:
        """Create a new book note from the template."""
        try:
            # Read template
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # Generate filename
            title_clean = re.sub(r'[^\w\s-]', '', book['title'])
            authors = book.get('authors', ['Unknown'])
            author_clean = re.sub(r'[^\w\s-]', '', authors[0])
            
            pub_date = book.get('publishedDate', '')
            year = ''
            if pub_date:
                year_match = re.search(r'\d{4}', pub_date)
                if year_match:
                    year = f" - {year_match.group()}"
            
            filename = f"{author_clean} - {title_clean}{year}.md"
            filepath = self.books_dir / filename
            
            # Handle cover image
            local_cover_filename = ""
            if book.get('coverUrl'):
                cover_filename = f"{author_clean} - {title_clean}{year}.jpg"
                local_cover_path = self.covers_dir / cover_filename
                local_cover_filename = f"References/Attachments/Book Search Covers/{cover_filename}"
                
                print("Downloading cover image...")
                if not self.api_client.download_cover(book['coverUrl'], local_cover_path):
                    print("Warning: Failed to download cover image")
                    local_cover_filename = ""
                else:
                    print(" Cover image downloaded")
            
            # Process template
            content = self._process_template(template, book, local_cover_filename)
            
            # Ensure books directory exists
            self.books_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if file already exists
            if filepath.exists():
                overwrite = input(f"File '{filename}' already exists. Overwrite? (y/n): ").strip().lower()
                if overwrite != 'y':
                    print("Book note creation cancelled.")
                    return False
            
            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Book note saved as: {filepath}")
            return True
            
        except Exception as e:
            print(f"Error creating book note: {e}")
            return False
    
    def _process_template(self, template: str, book: Dict, local_cover_filename: str) -> str:
        """Process the template with book data."""
        # Extract ISBN parts
        isbn_data = book.get('isbn', '')
        isbn10, isbn13 = '', ''
        
        if isbn_data:
            if ',' in isbn_data:
                parts = [p.strip() for p in isbn_data.split(',')]
                if len(parts) >= 2:
                    isbn10, isbn13 = parts[0], parts[1]
                else:
                    # Try to determine which is which by length
                    isbn_clean = parts[0].replace('-', '')
                    if len(isbn_clean) == 10:
                        isbn10 = parts[0]
                    elif len(isbn_clean) == 13:
                        isbn13 = parts[0]
            else:
                isbn_clean = isbn_data.replace('-', '')
                if len(isbn_clean) == 10:
                    isbn10 = isbn_data
                elif len(isbn_clean) == 13:
                    isbn13 = isbn_data
        
        # Get primary author for template
        authors = book.get('authors', ['Unknown'])
        primary_author = authors[0] if authors else 'Unknown'
        
        # Get primary category
        categories = book.get('categories', ['General'])
        primary_category = categories[0] if categories else 'General'
        
        # Format publish date
        publish_date = book.get('publishedDate', '')
        if publish_date and len(publish_date) == 4:  # Just year
            publish_date = f"{publish_date}-01-01"
        
        # Create current timestamp
        created_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Template replacements
        replacements = {
            '{{title}}': book.get('title', ''),
            '{{subtitle}}': book.get('subtitle', ''),
            '{{author}}': primary_author,
            '{{category}}': primary_category,
            '{{publisher}}': book.get('publisher', ''),
            '{{publishDate}}': publish_date,
            '{{totalPage}}': str(book.get('pageCount', '')),
            '{{isbn10}}': isbn10,
            '{{isbn13}}': isbn13,
            '{{coverUrl}}': book.get('coverUrl', ''),
            '{{localCoverImage}}': local_cover_filename
        }
        
        # Apply replacements
        content = template
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        
        # Add created timestamp (the template has an empty created field)
        content = content.replace('created: ', f'created: {created_timestamp}')
        
        return content


def main():
    creator = BookNoteCreator(TEMPLATE_PATH, BOOKS_DIR, COVERS_DIR)
    creator.run()


if __name__ == "__main__":
    main()