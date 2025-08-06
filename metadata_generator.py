#!/usr/bin/env python3
"""
Metadata Generator for Stake Scraper
=====================================

Generates comprehensive CSV and JSON metadata files for all scraped games
"""

import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime
import logging

class MetadataGenerator:
    """Generates metadata files from scraped game data"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def load_all_games_data(self, output_dir: Path) -> List[Dict]:
        """Load all games data from provider JSON files"""
        all_games = []
        providers_processed = 0
        
        # Convert to Path object if it's a string
        if isinstance(output_dir, str):
            output_dir = Path(output_dir)
        
        self.logger.info(f"🔍 Scanning for games data in: {output_dir}")
        
        # Scan all provider directories
        for provider_dir in output_dir.iterdir():
            if not provider_dir.is_dir():
                continue
            
            provider_name = provider_dir.name
            
            # Look for games files - support multiple formats
            games_files = []
            
            # Check for initial_games.json (new format)
            initial_games_file = provider_dir / "initial_games.json"
            if initial_games_file.exists():
                games_files.append(initial_games_file)
            
            # Also check for old format files
            games_files.extend(list(provider_dir.glob("*_games_*.json")))
            
            if not games_files:
                self.logger.warning(f"No games files found for provider: {provider_name}")
                continue
            
            provider_games = []
            
            # Load all games files for this provider
            for games_file in games_files:
                try:
                    with open(games_file, 'r', encoding='utf-8') as f:
                        games_data = json.load(f)
                        provider_games.extend(games_data.get('games', []))
                except Exception as e:
                    self.logger.error(f"Failed to load {games_file}: {e}")
            
            # Remove duplicates based on game_id
            unique_games = {}
            for game in provider_games:
                game_id = game.get('game_id')
                if game_id and game_id not in unique_games:
                    # Add file information
                    game['provider_directory'] = provider_name
                    game['webp_filename'] = self.generate_webp_filename(
                        game.get('provider', provider_name),
                        game.get('title', 'Unknown')
                    )
                    game['webp_path'] = str(provider_dir / game['webp_filename'])
                    game['webp_exists'] = (provider_dir / game['webp_filename']).exists()
                    
                    unique_games[game_id] = game
            
            games_count = len(unique_games)
            duplicates_removed = len(provider_games) - games_count
            
            self.logger.info(f"📊 {provider_name}: {games_count} unique games (removed {duplicates_removed} duplicates)")
            
            all_games.extend(unique_games.values())
            providers_processed += 1
        
        self.logger.info(f"✅ Loaded {len(all_games)} total games from {providers_processed} providers")
        return all_games
    
    def generate_webp_filename(self, provider_name: str, game_title: str) -> str:
        """Generate WebP filename matching the image processor format"""
        # Sanitize components
        clean_provider = self.sanitize_filename(provider_name)
        clean_title = self.sanitize_filename(game_title)
        
        # Create filename
        filename = f"{clean_provider} - {clean_title}.webp"
        
        return filename
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        import re
        
        # Remove HTML entities
        filename = filename.replace('&amp;', '&')
        
        # Remove invalid characters for Windows/Unix
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '', filename)
        
        # Replace multiple spaces with single space
        filename = re.sub(r'\s+', ' ', filename.strip())
        
        # Limit length
        max_length = 200
        if len(filename) > max_length:
            filename = filename[:max_length].strip()
        
        return filename
    
    def generate_csv_metadata(self, games_data: List[Dict], output_file: Path) -> None:
        """Generate CSV metadata file"""
        self.logger.info(f"📊 Generating CSV metadata: {output_file}")
        
        fieldnames = [
            'game_id',
            'title',
            'slug', 
            'provider',
            'provider_slug',
            'webp_filename',
            'webp_path',
            'webp_exists',
            'thumbnail_url',
            'player_count',
            'is_blocked',
            'is_widget_enabled',
            'categories',
            'themes',
            'provider_directory'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for game in games_data:
                # Prepare row data
                row = {}
                for field in fieldnames:
                    value = game.get(field, '')
                    
                    # Handle list fields
                    if field in ['categories', 'themes'] and isinstance(value, list):
                        value = '; '.join(value) if value else ''
                    
                    # Handle boolean fields
                    elif field in ['is_blocked', 'is_widget_enabled', 'webp_exists']:
                        value = str(value).lower() if value is not None else 'false'
                    
                    # Handle None values
                    elif value is None:
                        value = ''
                    
                    row[field] = value
                
                writer.writerow(row)
        
        self.logger.info(f"✅ CSV metadata saved: {len(games_data)} games")
    
    def generate_json_metadata(self, games_data: List[Dict], output_file: Path) -> None:
        """Generate JSON metadata file"""
        self.logger.info(f"📊 Generating JSON metadata: {output_file}")
        
        # Calculate statistics
        stats = self.calculate_statistics(games_data)
        
        metadata = {
            'generation_info': {
                'timestamp': datetime.now().isoformat(),
                'total_games': len(games_data),
                'generator': 'Robust Stake Scraper',
                'version': '1.0'
            },
            'statistics': stats,
            'games': games_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"✅ JSON metadata saved: {len(games_data)} games")
    
    def calculate_statistics(self, games_data: List[Dict]) -> Dict:
        """Calculate comprehensive statistics"""
        stats = {
            'total_games': len(games_data),
            'providers': {},
            'categories': {},
            'themes': {},
            'images': {
                'total_expected': len(games_data),
                'downloaded': 0,
                'missing': 0
            },
            'top_providers': [],
            'top_categories': [],
            'top_themes': []
        }
        
        # Count by provider
        provider_counts = {}
        category_counts = {}
        theme_counts = {}
        
        for game in games_data:
            # Provider stats
            provider = game.get('provider', 'Unknown')
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            # Image stats
            if game.get('webp_exists', False):
                stats['images']['downloaded'] += 1
            else:
                stats['images']['missing'] += 1
            
            # Category stats
            categories = game.get('categories', [])
            if isinstance(categories, list):
                for category in categories:
                    category_counts[category] = category_counts.get(category, 0) + 1
            
            # Theme stats
            themes = game.get('themes', [])
            if isinstance(themes, list):
                for theme in themes:
                    theme_counts[theme] = theme_counts.get(theme, 0) + 1
        
        # Sort and store top items
        stats['providers'] = dict(sorted(provider_counts.items(), key=lambda x: x[1], reverse=True))
        stats['categories'] = dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True))
        stats['themes'] = dict(sorted(theme_counts.items(), key=lambda x: x[1], reverse=True))
        
        # Top 10 lists
        stats['top_providers'] = list(stats['providers'].items())[:10]
        stats['top_categories'] = list(stats['categories'].items())[:10]
        stats['top_themes'] = list(stats['themes'].items())[:10]
        
        # Image completion rate
        if stats['images']['total_expected'] > 0:
            completion_rate = (stats['images']['downloaded'] / stats['images']['total_expected']) * 100
            stats['images']['completion_rate'] = round(completion_rate, 2)
        else:
            stats['images']['completion_rate'] = 0
        
        return stats
    
    def generate_provider_summary(self, games_data: List[Dict], output_file: Path) -> None:
        """Generate provider summary CSV"""
        self.logger.info(f"📊 Generating provider summary: {output_file}")
        
        provider_stats = {}
        
        for game in games_data:
            provider = game.get('provider', 'Unknown')
            provider_slug = game.get('provider_slug', '')
            
            if provider not in provider_stats:
                provider_stats[provider] = {
                    'provider_name': provider,
                    'provider_slug': provider_slug,
                    'total_games': 0,
                    'images_downloaded': 0,
                    'images_missing': 0,
                    'categories': set(),
                    'themes': set()
                }
            
            provider_stats[provider]['total_games'] += 1
            
            if game.get('webp_exists', False):
                provider_stats[provider]['images_downloaded'] += 1
            else:
                provider_stats[provider]['images_missing'] += 1
            
            # Collect categories and themes
            categories = game.get('categories', [])
            if isinstance(categories, list):
                provider_stats[provider]['categories'].update(categories)
            
            themes = game.get('themes', [])
            if isinstance(themes, list):
                provider_stats[provider]['themes'].update(themes)
        
        # Convert to CSV format
        fieldnames = [
            'provider_name',
            'provider_slug',
            'total_games',
            'images_downloaded',
            'images_missing',
            'completion_rate',
            'unique_categories',
            'unique_themes'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for provider, stats in sorted(provider_stats.items(), key=lambda x: x[1]['total_games'], reverse=True):
                completion_rate = 0
                if stats['total_games'] > 0:
                    completion_rate = round((stats['images_downloaded'] / stats['total_games']) * 100, 2)
                
                row = {
                    'provider_name': stats['provider_name'],
                    'provider_slug': stats['provider_slug'],
                    'total_games': stats['total_games'],
                    'images_downloaded': stats['images_downloaded'],
                    'images_missing': stats['images_missing'],
                    'completion_rate': f"{completion_rate}%",
                    'unique_categories': len(stats['categories']),
                    'unique_themes': len(stats['themes'])
                }
                
                writer.writerow(row)
        
        self.logger.info(f"✅ Provider summary saved: {len(provider_stats)} providers")
    
    def generate_all_metadata(self, output_dir: Path) -> Dict:
        """Generate all metadata files"""
        self.logger.info("📊 Starting metadata generation...")
        
        # Load all games data from the configured games directory
        games_dir = self.config if isinstance(self.config, str) else self.config.get('games_dir', 'stake_thumbnails')
        games_data = self.load_all_games_data(games_dir)
        
        if not games_data:
            self.logger.warning("No games data found!")
            return {'success': False, 'error': 'No games data found'}
        
        # Create metadata directory
        if isinstance(output_dir, str):
            metadata_dir = Path(output_dir)
        else:
            metadata_dir = Path(output_dir)
        metadata_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate CSV metadata (default: True)
        generate_csv = True if isinstance(self.config, str) else self.config.get('generate_csv', True)
        if generate_csv:
            csv_file = metadata_dir / f"games_metadata_{timestamp}.csv"
            self.generate_csv_metadata(games_data, csv_file)
        
        # Generate JSON metadata (default: True)
        generate_json = True if isinstance(self.config, str) else self.config.get('generate_json', True)
        if generate_json:
            json_file = metadata_dir / f"games_metadata_{timestamp}.json"
            self.generate_json_metadata(games_data, json_file)
        
        # Generate provider summary
        provider_summary_file = metadata_dir / f"provider_summary_{timestamp}.csv"
        self.generate_provider_summary(games_data, provider_summary_file)
        
        # Calculate final statistics
        stats = self.calculate_statistics(games_data)
        
        self.logger.info("✅ Metadata generation completed!")
        self.logger.info(f"📊 Final Statistics:")
        self.logger.info(f"   Total Games: {stats['total_games']}")
        self.logger.info(f"   Total Providers: {len(stats['providers'])}")
        self.logger.info(f"   Images Downloaded: {stats['images']['downloaded']}")
        self.logger.info(f"   Images Missing: {stats['images']['missing']}")
        self.logger.info(f"   Completion Rate: {stats['images']['completion_rate']}%")
        
        return {
            'success': True,
            'statistics': stats,
            'files_generated': {
                'csv_metadata': str(csv_file) if generate_csv else None,
                'json_metadata': str(json_file) if generate_json else None,
                'provider_summary': str(provider_summary_file)
            }
        }

def generate_metadata_standalone(output_dir: str, config_file: str = "robust_scraper_config.json"):
    """Standalone function to generate metadata"""
    import json
    
    # Load config
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Generate metadata
    generator = MetadataGenerator(config)
    result = generator.generate_all_metadata(Path(output_dir))
    
    return result

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "stake_thumbnails"
    
    result = generate_metadata_standalone(output_dir)
    print(f"Metadata generation result: {result}")
