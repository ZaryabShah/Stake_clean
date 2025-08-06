#!/usr/bin/env python3
"""
Stake Thumbnail Downloader
Downloads game thumbnails from stake.json files and converts them to WebP format
"""

import os
import json
import requests
import hashlib
import re
from pathlib import Path
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import time

class StakeThumbnailDownloader:
    def __init__(self, 
                 stake_folder=".",
                 output_dir="stake_thumbnails",
                 max_workers=10,
                 clean_output=False):
        """
        Initialize the thumbnail downloader
        
        Args:
            stake_folder: Path to folder containing stake.json files
            output_dir: Directory to save converted thumbnails
            max_workers: Number of concurrent download threads
            clean_output: Whether to clean output directory before starting
        """
        self.stake_folder = Path(stake_folder)
        self.output_dir = Path(output_dir)
        self.hashes_dir = self.output_dir / ".hashes"
        self.max_workers = max_workers
        self.clean_output = clean_output
        
        # Statistics
        self.stats = {
            'total_games': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'skipped_duplicates': 0,
            'converted_to_webp': 0
        }
        
        # Create directories
        self.output_dir.mkdir(exist_ok=True)
        self.hashes_dir.mkdir(exist_ok=True)
        
        # Clean output directory if requested
        if self.clean_output:
            self.clean_output_directory()
    
    def clean_output_directory(self):
        """Remove all files from output directory except .hashes"""
        print("Cleaning output directory...")
        import shutil
        
        for item in self.output_dir.iterdir():
            if item.name == ".hashes":
                continue  # Keep the hashes directory
            
            if item.is_file():
                item.unlink()
                print(f"Removed file: {item.name}")
            elif item.is_dir():
                shutil.rmtree(item)
                print(f"Removed directory: {item.name}")

    def sanitize_filename(self, filename):
        """Sanitize filename for Windows compatibility"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove extra spaces and dots
        filename = re.sub(r'\s+', ' ', filename.strip())
        filename = filename.replace('..', '.')
        
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
    
    def get_image_hash(self, image_data):
        """Get hash of image data to detect duplicates"""
        return hashlib.md5(image_data).hexdigest()
    
    def download_and_convert_image(self, url, output_path):
        """Download image and convert to WebP format"""
        try:
            # Check if file already exists
            if output_path.exists():
                print(f"[SKIP] File exists: {output_path.name}")
                self.stats['skipped_duplicates'] += 1
                return True
            
            # Download image
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            image_data = response.content
            image_hash = self.get_image_hash(image_data)
            
            # Check for duplicate hash
            hash_file = self.hashes_dir / f"{image_hash}.txt"
            if hash_file.exists():
                existing_file = hash_file.read_text().strip()
                print(f"[DUPLICATE] {output_path.name} -> {existing_file}")
                self.stats['skipped_duplicates'] += 1
                return True
            
            # Convert to WebP
            image = Image.open(BytesIO(image_data))
            image.save(output_path, 'WEBP', quality=85, optimize=True)
            
            # Save hash reference
            hash_file.write_text(output_path.name)
            
            print(f"[SUCCESS] {output_path.name}")
            self.stats['successful_downloads'] += 1
            self.stats['converted_to_webp'] += 1
            return True
            
        except Exception as e:
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            print(f"[ERROR] Failed to download {url}: {error_msg}")
            self.stats['failed_downloads'] += 1
            return False
    
    def process_provider_file(self, json_file):
        """Process a single provider JSON file"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract games list
            games = data.get('games', [])
            if not games:
                print(f"[SKIP] No games found in {json_file}")
                return
            
            # Extract provider name from multiple possible locations
            provider_name = None
            
            # Debug: Print what we're working with
            print(f"[DEBUG] File: {json_file}")
            print(f"[DEBUG] Has provider_name: {'provider_name' in data}")
            print(f"[DEBUG] Has provider: {'provider' in data}")
            if 'provider' in data:
                print(f"[DEBUG] Provider type: {type(data['provider'])}")
                print(f"[DEBUG] Provider value: {data['provider']}")
            
            # Method 1: Direct provider_name field (checkpoint format)
            if 'provider_name' in data:
                provider_name = data['provider_name']
                print(f"[DEBUG] Got provider from provider_name: {provider_name}")
            
            # Method 2: Nested provider object (new format)
            elif 'provider' in data:
                provider = data['provider']
                if isinstance(provider, dict):
                    # New format: provider is a dict
                    provider_name = provider.get('name', provider.get('slug', ''))
                    print(f"[DEBUG] Got provider from dict: {provider_name}")
                elif isinstance(provider, str):
                    # Old format: provider is a string
                    provider_name = provider
                    print(f"[DEBUG] Got provider from string: {provider_name}")
            
            # Method 3: Extract from directory name as fallback
            if not provider_name or provider_name.strip() == '':
                provider_name = json_file.parent.name.replace('_', ' ')
                print(f"[DEBUG] Got provider from directory: {provider_name}")
            
            # Clean up provider name
            provider_name = provider_name.strip()
            
            print(f"\nProcessing {provider_name}: {len(games)} games")
            
            # Create provider-specific directory
            provider_dir = self.output_dir / self.sanitize_filename(provider_name)
            provider_dir.mkdir(exist_ok=True)
            print(f"[INFO] Created directory: {provider_dir}")
            
            download_tasks = []
            
            for game in games:
                self.stats['total_games'] += 1
                
                # Extract game info - handle both formats
                title = ''
                thumbnail_url = ''
                
                if isinstance(game, dict):
                    # Format 1: Direct fields
                    title = game.get('title', game.get('name', 'Unknown Game'))
                    thumbnail_url = game.get('thumbnail_url', game.get('thumbnailUrl', ''))
                    
                    # Format 2: If no thumbnail_url, try other fields
                    if not thumbnail_url:
                        thumbnail_url = game.get('image_url', game.get('imageUrl', ''))
                else:
                    print(f"[WARNING] Unexpected game format: {type(game)}")
                    continue
                
                if not thumbnail_url:
                    print(f"[WARNING] No thumbnail URL for: {title}")
                    continue
                
                # Clean up title
                title = title.strip()
                if not title:
                    title = game.get('slug', 'Unknown Game')
                
                # Create filename: "ProviderName - GameTitle.webp"
                filename = f"{provider_name} - {title}.webp"
                filename = self.sanitize_filename(filename)
                output_path = provider_dir / filename
                
                download_tasks.append((thumbnail_url, output_path))
            
            # Process downloads with thread pool
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_url = {
                    executor.submit(self.download_and_convert_image, url, path): (url, path)
                    for url, path in download_tasks
                }
                
                for future in as_completed(future_to_url):
                    url, path = future_to_url[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        print(f"[ERROR] Exception downloading {url}: {str(e)}")
                        self.stats['failed_downloads'] += 1
            
        except Exception as e:
            print(f"[ERROR] Failed to process {json_file}: {str(e)}")
    
    def scan_and_download_all(self):
        """Scan for all checkpoint JSON files and download thumbnails"""
        print("Starting Stake Thumbnail Download & WebP Conversion")
        print(f"Input directory: {self.stake_folder}")
        print(f"Output directory: {self.output_dir}")
        print(f"Max workers: {self.max_workers}")
        print(f"Clean output: {self.clean_output}")
        print("-" * 60)
        
        # Find all JSON files in the stake folder (checkpoint files)
        json_files = []
        
        # Pattern 1: Look for checkpoint files directly in the folder
        if self.stake_folder.is_dir():
            # Look for provider checkpoint files
            for json_file in self.stake_folder.glob("provider_*_initial.json"):
                json_files.append(json_file)
            
            # If no checkpoint files found, look for any JSON files
            if not json_files:
                for json_file in self.stake_folder.glob("*.json"):
                    if not json_file.name.startswith('.'):  # Skip hidden files
                        json_files.append(json_file)
            
            # Pattern 2: Look in subdirectories for initial_games.json files (fallback)
            if not json_files:
                for provider_dir in self.stake_folder.iterdir():
                    if provider_dir.is_dir():
                        initial_games_file = provider_dir / "initial_games.json"
                        if initial_games_file.exists():
                            json_files.append(initial_games_file)
        
        if not json_files:
            print(f"No JSON files found in {self.stake_folder}!")
            print("Expected files:")
            print("  - provider_*_initial.json (checkpoint format)")
            print("  - */initial_games.json (directory format)")
            return
        
        print(f"Found {len(json_files)} JSON files to process")
        
        # Process each file
        for i, json_file in enumerate(json_files, 1):
            print(f"\n[{i}/{len(json_files)}] Processing: {json_file.relative_to(self.stake_folder)}")
            self.process_provider_file(json_file)
        
        # Print final statistics
        print("\n" + "=" * 60)
        print("DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Total games processed: {self.stats['total_games']}")
        print(f"Successful downloads: {self.stats['successful_downloads']}")
        print(f"Failed downloads: {self.stats['failed_downloads']}")
        print(f"Skipped duplicates: {self.stats['skipped_duplicates']}")
        print(f"Converted to WebP: {self.stats['converted_to_webp']}")
        
        if self.stats['total_games'] > 0:
            success_rate = (self.stats['successful_downloads'] / self.stats['total_games']) * 100
            print(f"Success rate: {success_rate:.1f}%")

def main():
    """Main function with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download and convert Stake game thumbnails to WebP')
    parser.add_argument('--input', '-i', default='.', 
                        help='Input directory containing stake.json files (default: current directory)')
    parser.add_argument('--output', '-o', default='stake_thumbnails', 
                        help='Output directory for thumbnails (default: stake_thumbnails)')
    parser.add_argument('--workers', '-w', type=int, default=10, 
                        help='Number of concurrent download threads (default: 10)')
    parser.add_argument('--clean', action='store_true', 
                        help='Clean output directory before starting')
    
    try:
        args = parser.parse_args()
        
        downloader = StakeThumbnailDownloader(
            stake_folder=args.input,
            output_dir=args.output,
            max_workers=args.workers,
            clean_output=args.clean
        )
        
        downloader.scan_and_download_all()
        
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")

if __name__ == "__main__":
    main()
