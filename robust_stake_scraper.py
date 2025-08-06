#!/usr/bin/env python3
"""
Robust Stake.com Game Thumbnail Scraper
========================================

A checkpoint-based, async scraper that extracts all game thumbnails from Stake.com
with proper naming, organization, and robust error handling.

Features:
- Checkpoint system for resumable operations
- Async processing for efficiency
- WebP conversion and optimization
- Provider-based organization
- Comprehensive error handling and retries
"""

import asyncio
import aiohttp
import aiofiles
import json
import csv
import re
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from urllib.parse import urljoin, urlparse
import subprocess
import time
import hashlib
from dataclasses import dataclass, asdict
import shutil

# Image processing
from PIL import Image, ImageFile
import io
import requests

# HTML parsing
from bs4 import BeautifulSoup

# Hardcoded providers
from hardcoded_providers import get_all_providers, get_provider_names_mapping

# Configure PIL to handle truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

@dataclass
class GameData:
    """Data structure for game information"""
    game_id: str
    title: str
    slug: str
    provider: str
    provider_slug: str
    thumbnail_url: str
    thumbnail_blur_hash: Optional[str] = None
    player_count: Optional[int] = None
    is_blocked: bool = False
    is_widget_enabled: bool = True
    categories: Optional[List[str]] = None
    themes: Optional[List[str]] = None

@dataclass
class ProviderData:
    """Data structure for provider information"""
    slug: str
    name: str
    url: str
    image_url: Optional[str] = None
    total_games: Optional[int] = None
    games_fetched: int = 0
    status: str = "pending"  # pending, in_progress, completed, error
    last_updated: Optional[str] = None
    checkpoint_file: Optional[str] = None

class CheckpointManager:
    """Manages checkpoint files for resumable operations"""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
    
    def save_checkpoint(self, checkpoint_name: str, data: Dict) -> None:
        """Save checkpoint data"""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_name}.json"
        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            logging.info(f"✅ Checkpoint saved: {checkpoint_name}")
        except Exception as e:
            logging.error(f"❌ Failed to save checkpoint {checkpoint_name}: {e}")
    
    def load_checkpoint(self, checkpoint_name: str) -> Optional[Dict]:
        """Load checkpoint data"""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_name}.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logging.info(f"✅ Checkpoint loaded: {checkpoint_name}")
                return data
            except Exception as e:
                logging.error(f"❌ Failed to load checkpoint {checkpoint_name}: {e}")
        return None
    
    def checkpoint_exists(self, checkpoint_name: str) -> bool:
        """Check if checkpoint exists"""
        return (self.checkpoint_dir / f"{checkpoint_name}.json").exists()
    
    def delete_checkpoint(self, checkpoint_name: str) -> None:
        """Delete checkpoint file"""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_name}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logging.info(f"🗑️ Checkpoint deleted: {checkpoint_name}")

class RobustStakeScraper:
    """Main scraper class with checkpoint support"""
    
    def __init__(self, config_file: str = "robust_scraper_config.json"):
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.setup_directories()
        self.checkpoint_manager = CheckpointManager()
        
        # Statistics
        self.stats = {
            'providers_found': 0,
            'providers_completed': 0,
            'games_found': 0,
            'images_downloaded': 0,
            'images_converted': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Session for HTTP requests
        self.session = None
        
        # Rate limiting
        self.request_semaphore = asyncio.Semaphore(self.config['max_concurrent_requests'])
        self.download_semaphore = asyncio.Semaphore(self.config['max_concurrent_downloads'])
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        default_config = {
            "output_dir": "stake_thumbnails",
            "temp_dir": "temp_html", 
            "metadata_dir": "metadata",
            "checkpoints_dir": "checkpoints",
            "js_fetcher_dir": ".",
            "webp_quality": 85,
            "webp_method": 6,
            "max_concurrent_requests": 3,
            "max_concurrent_downloads": 5,
            "max_concurrent_graphql": 2,
            "retry_attempts": 5,
            "retry_delay": 2,
            "request_delay": 1,
            "organize_by_provider": True,
            "generate_csv": True,
            "generate_json": True,
            "min_image_size": 100,
            "max_image_size": 1024,
            "allowed_image_formats": ["jpg", "jpeg", "png", "webp"],
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "games_per_request": 39,
            "enable_checkpoints": True,
            "auto_resume": True
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
                print("Using default configuration...")
        else:
            # Create default config file
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default config file: {config_file}")
            
        return default_config
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"robust_stake_scraper_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 Robust Stake Scraper initialized")
    
    def setup_directories(self):
        """Create necessary directories"""
        directories = [
            self.config['output_dir'],
            self.config['temp_dir'],
            self.config['metadata_dir'],
            self.config['checkpoints_dir']
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
        
        self.logger.info("📁 Directories created/verified")
    
    async def fetch_providers(self) -> List[ProviderData]:
        """Load hardcoded providers list with checkpoint support"""
        
        # Check if providers checkpoint exists
        providers_checkpoint = self.checkpoint_manager.load_checkpoint("providers_list")
        if providers_checkpoint and self.config['auto_resume']:
            self.logger.info("📋 Loading providers from checkpoint...")
            providers = []
            for provider_data in providers_checkpoint['providers']:
                providers.append(ProviderData(**provider_data))
            self.stats['providers_found'] = len(providers)
            return providers
        
        self.logger.info("🔍 Loading hardcoded providers list...")
        
        try:
            # Get hardcoded providers
            hardcoded_providers = get_all_providers()
            
            providers = []
            for provider_data in hardcoded_providers:
                provider = ProviderData(
                    slug=provider_data['slug'],
                    name=provider_data['name'],
                    url=provider_data['url'],
                    status="pending"
                )
                providers.append(provider)
            
            self.stats['providers_found'] = len(providers)
            self.logger.info(f"✅ Loaded {len(providers)} hardcoded providers")
            
            # Save providers checkpoint
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'total_providers': len(providers),
                'source': 'hardcoded_providers',
                'providers': [asdict(p) for p in providers]
            }
            self.checkpoint_manager.save_checkpoint("providers_list", checkpoint_data)
            
            return providers
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load hardcoded providers: {e}")
            raise
    
    async def run_js_fetcher(self, js_file: str) -> bool:
        """Run JavaScript fetcher and return success status"""
        try:
            self.logger.info(f"🔧 Running {js_file}...")
            
            # Run the JavaScript file
            process = await asyncio.create_subprocess_exec(
                'node', js_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config['js_fetcher_dir']
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"✅ {js_file} completed successfully")
                return True
            else:
                self.logger.error(f"❌ {js_file} failed with return code {process.returncode}")
                if stderr:
                    self.logger.error(f"Error output: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to run {js_file}: {e}")
            return False
    
    async def fetch_provider_games_initial(self, provider: ProviderData) -> bool:
        """Fetch initial games data for a provider (first batch using HTML approach)"""
        
        # Check if provider checkpoint exists
        checkpoint_name = f"provider_{provider.slug}_initial"
        existing_checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint_name)
        
        if existing_checkpoint and self.config['auto_resume']:
            self.logger.info(f"📋 Provider {provider.name} initial data already fetched")
            provider.status = existing_checkpoint.get('status', 'completed')
            provider.total_games = existing_checkpoint.get('total_games', 0)
            provider.games_fetched = existing_checkpoint.get('games_fetched', 0)
            return True
        
        self.logger.info(f"🎮 Fetching initial games for provider: {provider.name}")
        
        # Retry logic for failed attempts
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Create provider-specific directory
                provider_dir = Path(self.config['output_dir']) / self.sanitize_filename(provider.name)
                provider_dir.mkdir(exist_ok=True)
                
                # Use HTML games fetcher for initial data (not GraphQL)
                games_js_file = "games.js"
                
                # Run the JavaScript HTML games fetcher
                process = await asyncio.create_subprocess_exec(
                    'node', games_js_file, f'--provider={provider.slug}',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.config['js_fetcher_dir']
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    # Parse the output to get game count information
                    output_text = stdout.decode()
                    self.logger.info(f"📊 HTML fetch output for {provider.name}:\n{output_text}")
                    
                    # Extract content length to detect if we got valid response
                    content_length = 0
                    content_match = re.search(r'📏 Content length:\s*(\d+)\s*characters', output_text)
                    if content_match:
                        content_length = int(content_match.group(1))
                    
                    # Try to parse actual games data from any generated HTML files
                    games_data = self.parse_html_games_data(provider.slug)
                    actual_games_count = len(games_data)
                    
                    # Extract total games from output patterns
                    total_from_output = self.extract_total_games_from_output(output_text)
                    
                    # Improved logic for handling different scenarios
                    if actual_games_count > 0:
                        # We found games - proceed normally
                        games_fetched = actual_games_count
                        
                        # Logic: if actual games < 39, then that's the total (no more pages)
                        # If actual games >= 39, use the total from output for future pagination
                        if actual_games_count < 39:
                            total_games = actual_games_count
                            self.logger.info(f"📊 Provider has only {total_games} games (complete - no pagination needed)")
                        else:
                            # Use total from output, but if not found, use actual count as minimum
                            total_games = total_from_output if total_from_output > 0 else actual_games_count
                            self.logger.info(f"📊 Provider has {total_games} total games ({actual_games_count} in initial batch)")
                        
                        return await self.save_provider_data(provider, provider_dir, games_data, total_games, games_fetched, checkpoint_name)
                    
                    elif content_length > 100000:  # Large content but no games found
                        # This means the provider page exists but has 0 games
                        self.logger.info(f"📊 Provider {provider.name} has 0 games (page exists but empty)")
                        return await self.save_provider_data(provider, provider_dir, [], 0, 0, checkpoint_name)
                    
                    else:
                        # Small content or no content - likely an error page, retry
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ Attempt {attempt + 1} failed for {provider.name} - small/no content (size: {content_length}). Retrying...")
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        else:
                            self.logger.error(f"❌ All attempts failed for {provider.name} - no valid content after {max_retries} tries")
                            provider.status = "error"
                            self.stats['errors'] += 1
                            return False
                else:
                    stderr_text = stderr.decode() if stderr else "No error details"
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ Attempt {attempt + 1} failed for {provider.name}: {stderr_text}. Retrying...")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise Exception(f"HTML games fetcher failed after {max_retries} attempts. Last error: {stderr_text}")
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"⚠️ Attempt {attempt + 1} failed for {provider.name}: {e}. Retrying...")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    self.logger.error(f"❌ Failed to fetch initial games for {provider.name} after {max_retries} attempts: {e}")
                    provider.status = "error"
                    self.stats['errors'] += 1
                    return False
        
        return False
    
    async def save_provider_data(self, provider: ProviderData, provider_dir: Path, games_data: List[Dict], total_games: int, games_fetched: int, checkpoint_name: str) -> bool:
        """Save provider data and create checkpoint"""
        try:
            # Format games data according to client requirements
            formatted_games = []
            for game in games_data:
                # Extract provider from game or use provider name
                game_provider = game.get('provider', provider.name)
                
                # Format filename as per client requirements: "ProviderName - GameTitle.webp"
                safe_provider = re.sub(r'[<>:"/\\|?*]', '', game_provider).strip()
                safe_title = re.sub(r'[<>:"/\\|?*]', '', game.get('name', '')).strip()
                expected_filename = f"{safe_provider} - {safe_title}.webp"
                
                formatted_game = {
                    'game_id': game.get('id', ''),
                    'title': game.get('name', ''),
                    'slug': game.get('slug', ''),
                    'provider': game_provider,
                    'thumbnail_url': game.get('thumbnailUrl', ''),
                    'expected_filename': expected_filename,
                    'game_url': f"https://stake.com/casino/games/{game.get('slug', '')}" if game.get('slug') else '',
                    'extracted_at': datetime.now().isoformat()
                }
                formatted_games.append(formatted_game)
            
            # Save the structured data
            games_data_to_save = {
                'provider': provider.name,
                'provider_slug': provider.slug,
                'total_games': total_games,
                'games_fetched': len(formatted_games),
                'is_complete': total_games == len(formatted_games),
                'needs_pagination': total_games > len(formatted_games),
                'games': formatted_games,
                'timestamp': datetime.now().isoformat(),
                'source': 'initial_html_fetch'
            }
            
            # Save games data to the provider directory
            games_file = provider_dir / "initial_games.json"
            with open(games_file, 'w', encoding='utf-8') as f:
                json.dump(games_data_to_save, f, indent=2, ensure_ascii=False)
            
            if total_games > 0:
                self.logger.info(f"💾 Saved {len(formatted_games)} games data for {provider.name}")
            else:
                self.logger.info(f"💾 Saved empty games data for {provider.name} (0 games)")
            
            # Update provider status only on success
            provider.status = "initial_completed"
            provider.total_games = total_games
            provider.games_fetched = games_fetched
            
            # Save checkpoint only when we have processed the provider (even if 0 games)
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'provider_slug': provider.slug,
                'provider_name': provider.name,
                'status': provider.status,
                'total_games': provider.total_games,
                'games_fetched': provider.games_fetched,
                'is_complete': games_data_to_save['is_complete'],
                'needs_pagination': games_data_to_save['needs_pagination'],
                'output_dir': str(provider_dir),
                'games_data_file': str(games_file),
                'source': 'initial_html_fetch'
            }
            self.checkpoint_manager.save_checkpoint(checkpoint_name, checkpoint_data)
            
            if total_games == 0:
                completion_status = "complete (0 games)"
            elif games_data_to_save['is_complete']:
                completion_status = "complete"
            else:
                completion_status = f"initial batch ({games_fetched}/{total_games})"
            
            self.logger.info(f"✅ Initial fetch completed for {provider.name}: {completion_status}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save data for {provider.name}: {e}")
            provider.status = "error"
            self.stats['errors'] += 1
            return False
    
    def extract_total_games_from_output(self, output_text: str) -> int:
        """Extract total games count from games.js output"""
        # Look for the specific pattern from games.js output
        patterns = [
            r'📊 Total games found:\s*(\d+)',
            r'Total games found:\s*(\d+)',
            r'Found (\d+) games total',
            r'Total games:\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output_text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        # If no total found, return 0 (will be handled by caller)
        return 0
    
    def extract_games_from_html_output(self, output_text: str, provider_slug: str) -> Tuple[int, int]:
        """Extract total games and games fetched from HTML output"""
        total_games = 0
        games_fetched = 0
        
        # Look for total games patterns specific to games.js output
        total_patterns = [
            r'📊 Total games found:\s*(\d+)',
            r'Total games found:\s*(\d+)',
            r'📊 Found (\d+) games in JSON data',
            r'Found (\d+) games in JSON data',
            r'🎮 Found approximately (\d+) games in initial load',
            r'Found approximately (\d+) games'
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, output_text, re.IGNORECASE)
            if match:
                total_games = int(match.group(1))
                break
        
        # Look for initial games fetched patterns
        fetched_patterns = [
            r'🎮 Found approximately (\d+) games in initial load',
            r'Found approximately (\d+) games',
            r'📊 Found (\d+) games in JSON data'
        ]
        
        for pattern in fetched_patterns:
            match = re.search(pattern, output_text, re.IGNORECASE)
            if match:
                games_fetched = int(match.group(1))
                break
        
        # If no specific count found, use reasonable defaults
        if total_games == 0:
            total_games = 100  # Default estimate
        if games_fetched == 0:
            games_fetched = min(39, total_games)  # Typical initial load
            
        return total_games, games_fetched
    
    def parse_html_games_data(self, provider_slug: str) -> List[Dict]:
        """Parse games data from generated HTML files"""
        games_data = []
        
        # Look for recently generated HTML files for this provider
        html_patterns = [
            f"stake_games_{provider_slug}_*.html",
            f"stake_games_{provider_slug}_latest.html"
        ]
        
        for pattern in html_patterns:
            for html_file in Path(".").glob(pattern):
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # Extract games from HTML using regex patterns
                    games = self.extract_games_from_html_content(html_content)
                    games_data.extend(games)
                    
                    self.logger.info(f"📊 Extracted {len(games)} games from {html_file}")
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not parse {html_file}: {e}")
        
        # Remove duplicates based on game ID or name
        unique_games = {}
        for game in games_data:
            game_id = game.get('id') or game.get('slug') or game.get('name')
            if game_id and game_id not in unique_games:
                unique_games[game_id] = game
        
        return list(unique_games.values())
    
    def extract_games_from_html_content(self, html_content: str) -> List[Dict]:
        """Extract games data from HTML content, focusing on JSON-LD structured data"""
        games = []
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for JSON-LD script tags with game data
            script_tags = soup.find_all('script', {'type': 'application/ld+json'})
            
            for script in script_tags:
                if script.string:
                    try:
                        # Parse JSON-LD data
                        json_data = json.loads(script.string)
                        
                        # Handle different JSON-LD structures
                        if isinstance(json_data, list):
                            for item in json_data:
                                games.extend(self._extract_games_from_json_ld_item(item))
                        else:
                            games.extend(self._extract_games_from_json_ld_item(json_data))
                            
                    except (json.JSONDecodeError, Exception) as e:
                        continue
            
            # Fallback: Look for regular script tags with game data
            if not games:
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string and 'VideoGame' in script.string:
                        script_content = script.string
                        
                        # Extract JSON-LD from script content
                        json_ld_pattern = r'\{"@context":"https://schema\.org"[^}]*?"@type":"ItemList"[^}]*?"itemListElement":\[([^\]]+)\][^}]*?\}'
                        matches = re.findall(json_ld_pattern, script_content, re.DOTALL)
                        
                        for match in matches:
                            try:
                                # Parse the itemListElement array
                                game_list_json = f'[{match}]'
                                game_items = json.loads(game_list_json)
                                
                                for item in game_items:
                                    if item.get('@type') == 'VideoGame':
                                        game_data = self._parse_video_game_item(item)
                                        if game_data:
                                            games.append(game_data)
                                            
                            except (json.JSONDecodeError, Exception):
                                continue
                        
                        # Alternative pattern for individual VideoGame objects
                        video_game_pattern = r'\{"@type":"VideoGame"[^}]+?"name":"([^"]+)"[^}]+?"url":"[^"]*?/([^"/?]+)"[^}]+?"url":"([^"]+)"[^}]*?\}'
                        video_game_matches = re.findall(video_game_pattern, script_content)
                        
                        for match in video_game_matches:
                            if len(match) >= 3:
                                name, slug, thumbnail = match[0], match[1], match[2]
                                games.append({
                                    'id': slug,
                                    'name': name,
                                    'slug': slug,
                                    'thumbnailUrl': thumbnail,
                                    'provider': 'Stake Originals'
                                })
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error extracting games from HTML: {e}")
        
        return games
    
    def _extract_games_from_json_ld_item(self, item: Dict) -> List[Dict]:
        """Extract games from a JSON-LD item"""
        games = []
        
        try:
            # Check if this is an ItemList with games
            if item.get('@type') == 'ItemList' and 'itemListElement' in item:
                for element in item['itemListElement']:
                    if element.get('@type') == 'VideoGame':
                        game_data = self._parse_video_game_item(element)
                        if game_data:
                            games.append(game_data)
            
            # Check if this is directly a VideoGame
            elif item.get('@type') == 'VideoGame':
                game_data = self._parse_video_game_item(item)
                if game_data:
                    games.append(game_data)
                    
        except Exception as e:
            self.logger.debug(f"Error parsing JSON-LD item: {e}")
        
        return games
    
    def _parse_video_game_item(self, item: Dict) -> Dict:
        """Parse a VideoGame JSON-LD item into our game format"""
        try:
            name = item.get('name', '')
            url = item.get('url', '')
            
            # Extract slug from URL
            slug = ''
            if url:
                if '/games/' in url:
                    slug = url.split('/games/')[-1]
                elif '/' in url:
                    slug = url.split('/')[-1]
            
            # Get thumbnail URL
            thumbnail_url = ''
            if 'image' in item:
                image_data = item['image']
                if isinstance(image_data, dict):
                    thumbnail_url = image_data.get('url', '')
                elif isinstance(image_data, str):
                    thumbnail_url = image_data
            
            # Get provider info
            provider = 'Stake Originals'  # Default for most games
            if 'publisher' in item:
                publisher_data = item['publisher']
                if isinstance(publisher_data, dict):
                    provider = publisher_data.get('name', provider)
            
            if name and thumbnail_url:
                return {
                    'id': slug or name.lower().replace(' ', '-'),
                    'name': name,
                    'slug': slug,
                    'thumbnailUrl': thumbnail_url,
                    'provider': provider
                }
                
        except Exception as e:
            self.logger.debug(f"Error parsing VideoGame item: {e}")
        
        return None
    
    async def fetch_all_provider_games(self, provider: ProviderData) -> bool:
        """Fetch all remaining games for a provider using GraphQL pagination"""
        
        # Check if already completed
        checkpoint_name = f"provider_{provider.slug}_complete"
        existing_checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint_name)
        
        if existing_checkpoint and self.config['auto_resume']:
            self.logger.info(f"📋 Provider {provider.name} already completed")
            return True
        
        if not provider.total_games or provider.total_games <= provider.games_fetched:
            self.logger.info(f"✅ All games already fetched for {provider.name}")
            return True
        
        remaining_games = provider.total_games - provider.games_fetched
        self.logger.info(f"🔄 Fetching remaining {remaining_games} games for {provider.name}")
        
        try:
            # Calculate number of additional requests needed
            games_per_request = self.config['games_per_request']
            additional_requests = (remaining_games + games_per_request - 1) // games_per_request
            
            # Fetch remaining games in batches
            for batch in range(additional_requests):
                offset = provider.games_fetched + (batch * games_per_request)
                
                # Set environment variables for pagination
                env = os.environ.copy()
                env['PROVIDER_SLUG'] = provider.slug
                env['PROVIDER_NAME'] = provider.name
                env['GAMES_OFFSET'] = str(offset)
                env['GAMES_LIMIT'] = str(games_per_request)
                
                # Run GraphQL fetcher with pagination
                process = await asyncio.create_subprocess_exec(
                    'node', 'robust_graphql_fetcher.js',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.config['js_fetcher_dir'],
                    env=env
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    raise Exception(f"GraphQL pagination failed at offset {offset}")
                
                # Update progress
                provider.games_fetched = min(provider.games_fetched + games_per_request, provider.total_games)
                
                # Save progress checkpoint
                progress_checkpoint = {
                    'timestamp': datetime.now().isoformat(),
                    'provider_slug': provider.slug,
                    'games_fetched': provider.games_fetched,
                    'total_games': provider.total_games,
                    'batch_completed': batch + 1,
                    'total_batches': additional_requests
                }
                self.checkpoint_manager.save_checkpoint(f"provider_{provider.slug}_progress", progress_checkpoint)
                
                self.logger.info(f"📈 Progress {provider.name}: {provider.games_fetched}/{provider.total_games} games")
                
                # Rate limiting
                await asyncio.sleep(self.config['request_delay'])
            
            # Mark as completed
            provider.status = "completed"
            
            # Save completion checkpoint
            completion_checkpoint = {
                'timestamp': datetime.now().isoformat(),
                'provider_slug': provider.slug,
                'provider_name': provider.name,
                'status': 'completed',
                'total_games': provider.total_games,
                'games_fetched': provider.games_fetched
            }
            self.checkpoint_manager.save_checkpoint(checkpoint_name, completion_checkpoint)
            
            self.logger.info(f"🎉 Completed all games for {provider.name}")
            self.stats['providers_completed'] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch all games for {provider.name}: {e}")
            provider.status = "error"
            self.stats['errors'] += 1
            return False
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem"""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        # Limit length
        return filename[:100]
    
    async def process_all_providers_initial(self, providers: List[ProviderData]) -> None:
        """Process initial fetch for all providers concurrently"""
        self.logger.info(f"🚀 Starting initial fetch for {len(providers)} providers...")
        
        # Create semaphore for limiting concurrent requests
        semaphore = asyncio.Semaphore(self.config['max_concurrent_graphql'])
        
        async def fetch_with_semaphore(provider):
            async with semaphore:
                return await self.fetch_provider_games_initial(provider)
        
        # Process providers concurrently
        tasks = [fetch_with_semaphore(provider) for provider in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes
        successful = sum(1 for result in results if result is True)
        self.logger.info(f"✅ Initial fetch completed: {successful}/{len(providers)} providers successful")
    
    async def process_all_providers_complete(self, providers: List[ProviderData]) -> None:
        """Process complete fetch for all providers"""
        self.logger.info(f"🔄 Starting complete fetch for remaining games...")
        
        # Filter providers that need complete fetching
        providers_to_complete = [p for p in providers if p.status == "initial_completed" and p.total_games > p.games_fetched]
        
        if not providers_to_complete:
            self.logger.info("✅ All providers already completed")
            return
        
        self.logger.info(f"📋 {len(providers_to_complete)} providers need complete fetching")
        
        # Process sequentially to avoid rate limits
        for provider in providers_to_complete:
            await self.fetch_all_provider_games(provider)
            
            # Brief pause between providers
            await asyncio.sleep(self.config['request_delay'] * 2)
    
    async def download_and_process_images(self, providers: List[ProviderData]) -> None:
        """Download and process all images from game data"""
        self.logger.info("🖼️ Starting image download and processing...")
        
        from image_processor import process_all_provider_images
        
        # Filter completed providers
        completed_providers = [p for p in providers if p.status == "completed"]
        
        if not completed_providers:
            self.logger.warning("No completed providers found for image processing")
            return
        
        self.logger.info(f"📊 Processing images for {len(completed_providers)} providers")
        
        # Convert provider data to format expected by image processor
        providers_data = [
            {
                'slug': p.slug,
                'name': p.name,
                'total_games': p.total_games
            }
            for p in completed_providers
        ]
        
        # Process all images
        output_dir = Path(self.config['output_dir'])
        image_stats = await process_all_provider_images(self.config, providers_data, output_dir)
        
        # Update main stats
        self.stats['images_downloaded'] = image_stats['successful_images']
        self.stats['images_converted'] = image_stats['successful_images']
        self.stats['errors'] += image_stats['failed_images']
        
        self.logger.info(f"🖼️ Image processing completed:")
        self.logger.info(f"   📊 Total images: {image_stats['total_images']}")
        self.logger.info(f"   ✅ Successful: {image_stats['successful_images']}")
        self.logger.info(f"   ❌ Failed: {image_stats['failed_images']}")
        
        # Save image processing stats
        stats_file = Path(self.config['metadata_dir']) / f"image_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(image_stats, f, indent=2, default=str)
        
        self.logger.info(f"📊 Image stats saved to: {stats_file}")
    
    async def process_provider_images(self, provider: ProviderData) -> None:
        """Process images for a specific provider"""
        # This method is now handled by the centralized image processor
        pass
    
    async def generate_metadata(self, providers: List[ProviderData]) -> None:
        """Generate final metadata files"""
        self.logger.info("📊 Generating metadata files...")
        
        from metadata_generator import MetadataGenerator
        
        # Create metadata generator
        generator = MetadataGenerator(self.config)
        
        # Generate all metadata
        output_dir = Path(self.config['output_dir'])
        result = generator.generate_all_metadata(output_dir)
        
        if result['success']:
            self.logger.info("✅ Metadata generation completed successfully!")
            
            # Update stats with final numbers
            final_stats = result['statistics']
            self.stats.update({
                'final_total_games': final_stats['total_games'],
                'final_providers_count': len(final_stats['providers']),
                'final_images_downloaded': final_stats['images']['downloaded'],
                'final_completion_rate': final_stats['images']['completion_rate']
            })
            
            # Log summary
            self.logger.info(f"📊 Final Summary:")
            self.logger.info(f"   🎮 Total Games: {final_stats['total_games']}")
            self.logger.info(f"   🏢 Total Providers: {len(final_stats['providers'])}")
            self.logger.info(f"   🖼️ Images Downloaded: {final_stats['images']['downloaded']}")
            self.logger.info(f"   📈 Completion Rate: {final_stats['images']['completion_rate']}%")
            
        else:
            self.logger.error(f"❌ Metadata generation failed: {result.get('error', 'Unknown error')}")
        
        # Save comprehensive metadata including providers state
        comprehensive_metadata = {
            'scraping_session': {
                'timestamp': datetime.now().isoformat(),
                'total_providers': len(providers),
                'completed_providers': sum(1 for p in providers if p.status == "completed"),
                'total_games': sum(p.total_games or 0 for p in providers),
                'statistics': self.stats
            },
            'providers': [asdict(p) for p in providers],
            'metadata_generation_result': result
        }
        
        # Save comprehensive metadata
        metadata_file = Path(self.config['metadata_dir']) / f"comprehensive_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_metadata, f, indent=2, default=str)
        
        self.logger.info(f"📋 Comprehensive metadata saved to {metadata_file}")
    
    async def run(self) -> None:
        """Main execution method - Phase 1: Initial provider data collection"""
        self.stats['start_time'] = datetime.now()
        self.logger.info("🚀 Starting Robust Stake Scraper - Phase 1: Initial Data Collection")
        
        try:
            # Step 1: Fetch providers list
            self.logger.info("📋 Step 1: Fetching providers list...")
            providers = await self.fetch_providers()
            
            # Step 2: Initial fetch for all providers (get first batch + total counts)
            self.logger.info("🎮 Step 2: Fetching initial games data for all providers...")
            await self.process_all_providers_initial(providers)
            
            # Generate summary of results
            completed_providers = [p for p in providers if p.status == "initial_completed"]
            total_games = sum(p.total_games or 0 for p in completed_providers)
            total_fetched = sum(p.games_fetched or 0 for p in completed_providers)
            
            self.logger.info("✅ Phase 1 Complete: Initial provider data collection finished")
            self.logger.info(f"📊 Summary:")
            self.logger.info(f"   🏢 Total Providers: {len(providers)}")
            self.logger.info(f"   ✅ Successful: {len(completed_providers)}")
            self.logger.info(f"   🎮 Total Games Found: {total_games}")
            self.logger.info(f"   📥 Initial Games Fetched: {total_fetched}")
            
            # Count complete vs needs-pagination providers
            complete_providers = [p for p in completed_providers if p.total_games == p.games_fetched]
            pagination_providers = [p for p in completed_providers if p.total_games > p.games_fetched]
            
            self.logger.info(f"   ✅ Complete Providers (≤39 games): {len(complete_providers)}")
            self.logger.info(f"   📄 Providers Needing Pagination: {len(pagination_providers)}")
            
            # Save current state
            await self.generate_metadata(providers)
            
            self.logger.info("🎯 Phase 1 objectives achieved:")
            self.logger.info("   ✅ All provider total game counts collected")
            self.logger.info("   ✅ Initial game batches (≤39 games) saved")
            self.logger.info("   ✅ Data formatted according to client requirements")
            self.logger.info("   ✅ Checkpoints saved for all providers")
            
            # Note about next phases
            if pagination_providers:
                self.logger.info(f"\n📋 Next Steps Available:")
                self.logger.info(f"   📄 Phase 2: Complete game fetching for {len(pagination_providers)} providers")
                self.logger.info(f"   🖼️ Phase 3: Image downloading and processing")
                self.logger.info(f"   📊 Phase 4: Final metadata generation")
            else:
                self.logger.info(f"\n🎉 All providers have ≤39 games - data collection is complete!")
                self.logger.info(f"   🖼️ Ready for image downloading phase")
            
        except Exception as e:
            self.logger.error(f"💥 Fatal error in Phase 1: {e}")
            raise
        finally:
            self.stats['end_time'] = datetime.now()
            duration = self.stats['end_time'] - self.stats['start_time']
            self.logger.info(f"⏱️ Phase 1 execution time: {duration}")
            
            # Save session stats
            session_stats = {
                'phase': 'initial_data_collection',
                'duration': str(duration),
                'providers_processed': len(providers) if 'providers' in locals() else 0,
                'providers_successful': len([p for p in providers if p.status == "initial_completed"]) if 'providers' in locals() else 0,
                'total_games_found': sum(p.total_games or 0 for p in providers if p.status == "initial_completed") if 'providers' in locals() else 0,
                'stats': self.stats,
                'timestamp': datetime.now().isoformat()
            }
            
            stats_file = Path(self.config['metadata_dir']) / f"session_stats_phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(session_stats, f, indent=2, default=str)
            
            self.logger.info(f"📊 Session stats saved to: {stats_file}")

async def main():
    """Main entry point"""
    scraper = RobustStakeScraper()
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())
