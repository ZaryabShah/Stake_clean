#!/usr/bin/env python3
"""
Image Processor for Stake Scraper
==================================

Handles downloading, converting, and organizing game thumbnails in WebP format
with proper naming: "ProviderName - GameTitle.webp"
"""

import asyncio
import aiohttp
import aiofiles
import json
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
import hashlib

# Image processing
from PIL import Image, ImageFile
import io
import requests

# Configure PIL to handle truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

class ImageProcessor:
    """Handles image downloading and WebP conversion"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.session = None
        self.stats = {
            'images_downloaded': 0,
            'images_converted': 0,
            'images_skipped': 0,
            'errors': 0
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': self.config['user_agent']}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        # Remove HTML entities
        filename = filename.replace('&amp;', '&')
        
        # Remove invalid characters for Windows/Unix
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '', filename)
        
        # Replace multiple spaces with single space
        filename = re.sub(r'\s+', ' ', filename.strip())
        
        # Limit length to prevent filesystem issues
        max_length = 200  # Leave room for provider name and extension
        if len(filename) > max_length:
            filename = filename[:max_length].strip()
        
        return filename
    
    def generate_webp_filename(self, provider_name: str, game_title: str) -> str:
        """Generate WebP filename in format: ProviderName - GameTitle.webp"""
        # Sanitize components
        clean_provider = self.sanitize_filename(provider_name)
        clean_title = self.sanitize_filename(game_title)
        
        # Create filename
        filename = f"{clean_provider} - {clean_title}.webp"
        
        # Final sanitization
        filename = self.sanitize_filename(filename)
        
        return filename
    
    async def download_image(self, url: str, max_retries: int = 3) -> Optional[bytes]:
        """Download image from URL with retries"""
        if not url or not url.startswith(('http://', 'https://')):
            logging.warning(f"Invalid URL: {url}")
            return None
        
        for attempt in range(max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Validate minimum size
                        if len(content) < self.config['min_image_size']:
                            logging.warning(f"Image too small: {len(content)} bytes from {url}")
                            return None
                        
                        return content
                    else:
                        logging.warning(f"HTTP {response.status} for {url}")
                        
            except Exception as e:
                logging.warning(f"Download attempt {attempt + 1} failed for {url}: {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # Progressive delay
        
        self.stats['errors'] += 1
        return None
    
    def convert_to_webp(self, image_data: bytes, quality: int = None) -> Optional[bytes]:
        """Convert image data to WebP format"""
        if quality is None:
            quality = self.config['webp_quality']
        
        try:
            # Open image with PIL
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if image is too large
                max_size = self.config['max_image_size']
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Convert to WebP
                webp_buffer = io.BytesIO()
                img.save(
                    webp_buffer,
                    format='WEBP',
                    quality=quality,
                    method=self.config['webp_method'],
                    optimize=True
                )
                
                webp_data = webp_buffer.getvalue()
                self.stats['images_converted'] += 1
                
                return webp_data
                
        except Exception as e:
            logging.error(f"WebP conversion failed: {e}")
            self.stats['errors'] += 1
            return None
    
    async def process_game_image(self, game_data: Dict, provider_dir: Path) -> bool:
        """Process a single game's thumbnail image"""
        try:
            # Generate filename
            webp_filename = self.generate_webp_filename(
                game_data['provider'],
                game_data['title']
            )
            
            output_path = provider_dir / webp_filename
            
            # Skip if already exists
            if output_path.exists():
                logging.info(f"⏭️ Skipping existing file: {webp_filename}")
                self.stats['images_skipped'] += 1
                return True
            
            # Download image
            thumbnail_url = game_data['thumbnail_url']
            if not thumbnail_url:
                logging.warning(f"No thumbnail URL for game: {game_data['title']}")
                return False
            
            # Handle imgix URLs with auto format
            if 'imgix.net' in thumbnail_url and 'auto=format' not in thumbnail_url:
                # Add auto=format parameter for better format detection
                separator = '&' if '?' in thumbnail_url else '?'
                thumbnail_url += f"{separator}auto=format"
            
            logging.info(f"📥 Downloading: {game_data['title']} from {thumbnail_url}")
            
            image_data = await self.download_image(thumbnail_url)
            if not image_data:
                logging.error(f"Failed to download image for: {game_data['title']}")
                return False
            
            self.stats['images_downloaded'] += 1
            
            # Convert to WebP
            webp_data = self.convert_to_webp(image_data)
            if not webp_data:
                logging.error(f"Failed to convert image for: {game_data['title']}")
                return False
            
            # Save WebP file
            async with aiofiles.open(output_path, 'wb') as f:
                await f.write(webp_data)
            
            # Calculate size reduction
            original_size = len(image_data)
            webp_size = len(webp_data)
            reduction = ((original_size - webp_size) / original_size) * 100
            
            logging.info(f"✅ Saved: {webp_filename} ({webp_size:,} bytes, {reduction:.1f}% reduction)")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to process image for {game_data.get('title', 'unknown')}: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_provider_images(self, provider_slug: str, provider_name: str, 
                                     games_data: List[Dict], output_dir: Path) -> Dict:
        """Process all images for a provider"""
        
        provider_dir = output_dir / self.sanitize_filename(provider_name)
        provider_dir.mkdir(exist_ok=True)
        
        logging.info(f"🎯 Processing {len(games_data)} images for provider: {provider_name}")
        
        # Process images with concurrency control
        semaphore = asyncio.Semaphore(self.config['max_concurrent_downloads'])
        
        async def process_with_semaphore(game_data):
            async with semaphore:
                return await self.process_game_image(game_data, provider_dir)
        
        # Process all games concurrently
        tasks = [process_with_semaphore(game) for game in games_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        successful = sum(1 for result in results if result is True)
        failed = len(results) - successful
        
        provider_stats = {
            'provider': provider_name,
            'total_games': len(games_data),
            'successful_downloads': successful,
            'failed_downloads': failed,
            'output_directory': str(provider_dir)
        }
        
        logging.info(f"✅ Provider {provider_name} completed: {successful}/{len(games_data)} images processed")
        
        return provider_stats

async def process_all_provider_images(config: Dict, providers_data: List[Dict], 
                                    output_dir: Path) -> Dict:
    """Process images for all providers"""
    
    all_stats = {
        'total_providers': len(providers_data),
        'processed_providers': 0,
        'total_images': 0,
        'successful_images': 0,
        'failed_images': 0,
        'providers': []
    }
    
    async with ImageProcessor(config) as processor:
        
        for provider_data in providers_data:
            try:
                provider_slug = provider_data['slug']
                provider_name = provider_data['name']
                
                # Find games files for this provider
                provider_output_dir = output_dir / processor.sanitize_filename(provider_name)
                
                # Look for games JSON files
                games_files = list(provider_output_dir.glob(f"{provider_slug}_games_*.json"))
                
                if not games_files:
                    logging.warning(f"No games files found for provider: {provider_name}")
                    continue
                
                # Load all games data
                all_games = []
                for games_file in games_files:
                    try:
                        with open(games_file, 'r', encoding='utf-8') as f:
                            games_data = json.load(f)
                            all_games.extend(games_data.get('games', []))
                    except Exception as e:
                        logging.error(f"Failed to load games file {games_file}: {e}")
                
                if not all_games:
                    logging.warning(f"No games found for provider: {provider_name}")
                    continue
                
                # Remove duplicates based on game_id
                unique_games = {}
                for game in all_games:
                    game_id = game.get('game_id')
                    if game_id and game_id not in unique_games:
                        unique_games[game_id] = game
                
                unique_games_list = list(unique_games.values())
                logging.info(f"📊 Provider {provider_name}: {len(unique_games_list)} unique games (removed {len(all_games) - len(unique_games_list)} duplicates)")
                
                # Process images for this provider
                provider_stats = await processor.process_provider_images(
                    provider_slug, provider_name, unique_games_list, output_dir
                )
                
                all_stats['providers'].append(provider_stats)
                all_stats['processed_providers'] += 1
                all_stats['total_images'] += provider_stats['total_games']
                all_stats['successful_images'] += provider_stats['successful_downloads']
                all_stats['failed_images'] += provider_stats['failed_downloads']
                
            except Exception as e:
                logging.error(f"Failed to process provider {provider_data.get('name', 'unknown')}: {e}")
    
    # Add processor stats
    all_stats['processor_stats'] = processor.stats
    
    return all_stats

# Test function
async def test_image_processor():
    """Test the image processor with sample data"""
    config = {
        'webp_quality': 85,
        'webp_method': 6,
        'max_concurrent_downloads': 3,
        'min_image_size': 100,
        'max_image_size': 1024,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Sample game data
    sample_games = [
        {
            'game_id': 'test1',
            'title': 'Test Game 1',
            'provider': 'Test Provider',
            'thumbnail_url': 'https://mediumrare.imgix.net/sample1.jpg'
        }
    ]
    
    output_dir = Path('test_thumbnails')
    output_dir.mkdir(exist_ok=True)
    
    async with ImageProcessor(config) as processor:
        provider_stats = await processor.process_provider_images(
            'test-provider', 'Test Provider', sample_games, output_dir
        )
        print(f"Test completed: {provider_stats}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_image_processor())
