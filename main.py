#!/usr/bin/env python3
"""
Stake.com Complete Game Thumbnail Scraper
==========================================

Main orchestrator script that runs the complete 3-phase pipeline:
1. Initial data scraping with robust_stake_scraper.py
2. Complete provider data fetching with complete_all_providers_parallel.js
3. Thumbnail downloading and WebP conversion with thumbnail_downloader_fixed.py

This script manages the entire workflow and provides comprehensive logging.
"""

import os
import sys
import subprocess
import time
import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse

class StakeScraperOrchestrator:
    def __init__(self, clean_start=False, skip_scraping=False, skip_completion=False, skip_download=False):
        """
        Initialize the orchestrator
        
        Args:
            clean_start: Whether to clean all directories before starting
            skip_scraping: Skip the initial scraping step
            skip_completion: Skip the provider completion step
            skip_download: Skip the thumbnail download step
        """
        self.clean_start = clean_start
        self.skip_scraping = skip_scraping
        self.skip_completion = skip_completion
        self.skip_download = skip_download
        
        # Define project paths
        self.project_root = Path(__file__).parent
        self.checkpoints_dir = self.project_root / "checkpoints"
        self.metadata_dir = self.project_root / "metadata"
        self.stake_thumbnails_dir = self.project_root / "stake_thumbnails"
        self.stake_thumbnails_final_dir = self.project_root / "stake_thumbnails_final"
        self.logs_dir = self.project_root / "logs"
        self.temp_dir = self.project_root / "temp_html"
        
        # Scripts to run
        self.scripts = {
            'scraper': 'robust_stake_scraper.py',
            'completion': 'complete_all_providers_parallel.js',
            'downloader': 'thumbnail_downloader_fixed.py'
        }
        
        # Statistics (initialize before setup_logging)
        self.stats = {
            'start_time': datetime.now(),
            'end_time': None,
            'scraping_duration': None,
            'completion_duration': None,
            'download_duration': None,
            'total_providers': 0,
            'total_games': 0,
            'total_thumbnails': 0,
            'errors': []
        }
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging and directories"""
        # Create necessary directories
        directories = [
            self.checkpoints_dir,
            self.metadata_dir,
            self.stake_thumbnails_dir,
            self.stake_thumbnails_final_dir,
            self.logs_dir,
            self.temp_dir
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True)
        
        # Setup log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.logs_dir / f"stake_scraper_main_{timestamp}.log"
        
        print(f"🚀 Stake.com Complete Game Thumbnail Scraper")
        print(f"=" * 60)
        print(f"📁 Project root: {self.project_root}")
        print(f"📝 Log file: {self.log_file}")
        print(f"🕒 Start time: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"=" * 60)
    
    def log(self, message, level="INFO"):
        """Log message to both console and file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        print(log_message)
        
        # Write to log file
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def clean_directories(self):
        """Clean all output directories"""
        if not self.clean_start:
            return
            
        self.log("🧹 Cleaning directories for fresh start...")
        
        directories_to_clean = [
            self.checkpoints_dir,
            self.metadata_dir,
            self.stake_thumbnails_dir,
            self.stake_thumbnails_final_dir,
            self.temp_dir
        ]
        
        for directory in directories_to_clean:
            if directory.exists():
                try:
                    shutil.rmtree(directory)
                    directory.mkdir(exist_ok=True)
                    self.log(f"   ✅ Cleaned: {directory.name}")
                except Exception as e:
                    self.log(f"   ❌ Failed to clean {directory.name}: {str(e)}", "ERROR")
                    self.stats['errors'].append(f"Clean {directory.name}: {str(e)}")
    
    def check_dependencies(self):
        """Check if all required files and dependencies exist"""
        self.log("🔍 Checking dependencies...")
        
        # Check Python scripts
        required_files = [
            'robust_stake_scraper.py',
            'thumbnail_downloader_fixed.py',
            'complete_all_providers_parallel.js',
            'hardcoded_providers.py'
        ]
        
        missing_files = []
        for file in required_files:
            file_path = self.project_root / file
            if not file_path.exists():
                missing_files.append(file)
                self.log(f"   ❌ Missing: {file}", "ERROR")
            else:
                self.log(f"   ✅ Found: {file}")
        
        if missing_files:
            raise FileNotFoundError(f"Missing required files: {', '.join(missing_files)}")
        
        # Check Node.js availability
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                self.log(f"   ✅ Node.js: {result.stdout.strip()}")
            else:
                raise FileNotFoundError("Node.js not found")
        except FileNotFoundError:
            self.log("   ❌ Node.js not found. Please install Node.js to run JavaScript files.", "ERROR")
            raise
        
        # Check Python packages
        required_packages = ['requests', 'pillow', 'beautifulsoup4', 'aiohttp']
        missing_packages = []
        
        for package in required_packages:
            try:
                if package == 'pillow':
                    __import__('PIL')
                elif package == 'beautifulsoup4':
                    __import__('bs4')
                else:
                    __import__(package)
                self.log(f"   ✅ Python package: {package}")
            except ImportError:
                missing_packages.append(package)
                self.log(f"   ❌ Missing Python package: {package}", "ERROR")
        
        if missing_packages:
            self.log(f"   💡 Install missing packages: pip install {' '.join(missing_packages)}", "WARNING")
    
    def run_python_script(self, script_name, args=None):
        """Run a Python script and return success status"""
        script_path = self.project_root / script_name
        cmd = [sys.executable, str(script_path)]
        
        if args:
            cmd.extend(args)
        
        self.log(f"🐍 Running Python script: {script_name}")
        self.log(f"   Command: {' '.join(cmd)}")
        
        try:
            # Run the script and capture output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_root,
                universal_newlines=True
            )
            
            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(f"   📋 {output.strip()}")
                    
                    # Write to log file
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(f"   📋 {output.strip()}\n")
            
            return_code = process.poll()
            
            if return_code == 0:
                self.log(f"   ✅ {script_name} completed successfully")
                return True
            else:
                self.log(f"   ❌ {script_name} failed with return code {return_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"   ❌ Error running {script_name}: {str(e)}", "ERROR")
            self.stats['errors'].append(f"{script_name}: {str(e)}")
            return False
    
    def run_node_script(self, script_name):
        """Run a Node.js script and return success status"""
        script_path = self.project_root / script_name
        cmd = ['node', str(script_path)]
        
        self.log(f"🟨 Running Node.js script: {script_name}")
        self.log(f"   Command: {' '.join(cmd)}")
        
        try:
            # Run the script and capture output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_root,
                universal_newlines=True,
                shell=True
            )
            
            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(f"   📋 {output.strip()}")
                    
                    # Write to log file
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(f"   📋 {output.strip()}\n")
            
            return_code = process.poll()
            
            if return_code == 0:
                self.log(f"   ✅ {script_name} completed successfully")
                return True
            else:
                self.log(f"   ❌ {script_name} failed with return code {return_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"   ❌ Error running {script_name}: {str(e)}", "ERROR")
            self.stats['errors'].append(f"{script_name}: {str(e)}")
            return False
    
    def step_1_initial_scraping(self):
        """Step 1: Run initial scraping with robust_stake_scraper.py"""
        if self.skip_scraping:
            self.log("⏭️ Skipping initial scraping step")
            return True
            
        self.log("\n" + "=" * 60)
        self.log("📋 STEP 1: Initial Game Data Scraping")
        self.log("=" * 60)
        
        start_time = time.time()
        
        # Run the robust scraper
        success = self.run_python_script('robust_stake_scraper.py')
        
        duration = time.time() - start_time
        self.stats['scraping_duration'] = duration
        
        if success:
            self.log(f"✅ Step 1 completed in {duration:.1f} seconds")
            
            # Count checkpoints created
            if self.checkpoints_dir.exists():
                checkpoint_files = list(self.checkpoints_dir.glob("*.json"))
                self.stats['total_providers'] = len(checkpoint_files)
                self.log(f"📊 Created {len(checkpoint_files)} provider checkpoints")
        else:
            self.log("❌ Step 1 failed", "ERROR")
            
        return success
    
    def step_2_complete_providers(self):
        """Step 2: Complete provider data with complete_all_providers_parallel.js"""
        if self.skip_completion:
            self.log("⏭️ Skipping provider completion step")
            return True
            
        self.log("\n" + "=" * 60)
        self.log("📋 STEP 2: Complete Provider Data Fetching")
        self.log("=" * 60)
        
        start_time = time.time()
        
        # Run the parallel completion script
        success = self.run_node_script('complete_all_providers_parallel.js')
        
        duration = time.time() - start_time
        self.stats['completion_duration'] = duration
        
        if success:
            self.log(f"✅ Step 2 completed in {duration:.1f} seconds")
            
            # Count games in checkpoints
            total_games = 0
            if self.checkpoints_dir.exists():
                for checkpoint_file in self.checkpoints_dir.glob("*.json"):
                    try:
                        with open(checkpoint_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            games = data.get('games', [])
                            total_games += len(games)
                    except:
                        pass
                
                self.stats['total_games'] = total_games
                self.log(f"📊 Total games available: {total_games}")
        else:
            self.log("❌ Step 2 failed", "ERROR")
            
        return success
    
    def step_3_download_thumbnails(self):
        """Step 3: Download and convert thumbnails with thumbnail_downloader_fixed.py"""
        if self.skip_download:
            self.log("⏭️ Skipping thumbnail download step")
            return True
            
        self.log("\n" + "=" * 60)
        self.log("📋 STEP 3: Thumbnail Download & WebP Conversion")
        self.log("=" * 60)
        
        start_time = time.time()
        
        # Prepare arguments for the downloader as specified by user
        args = [
            '--input', str(self.checkpoints_dir),
            '--output', str(self.stake_thumbnails_final_dir),
            '--workers', '15'
        ]
        
        if self.clean_start:
            args.append('--clean')
        
        # Run the thumbnail downloader
        success = self.run_python_script('thumbnail_downloader_fixed.py', args)
        
        duration = time.time() - start_time
        self.stats['download_duration'] = duration
        
        if success:
            self.log(f"✅ Step 3 completed in {duration:.1f} seconds")
            
            # Count downloaded thumbnails
            if self.stake_thumbnails_final_dir.exists():
                webp_files = list(self.stake_thumbnails_final_dir.rglob("*.webp"))
                self.stats['total_thumbnails'] = len(webp_files)
                self.log(f"📊 Downloaded thumbnails: {len(webp_files)}")
        else:
            self.log("❌ Step 3 failed", "ERROR")
            
        return success
    
    def generate_final_report(self):
        """Generate final completion report"""
        self.stats['end_time'] = datetime.now()
        total_duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        self.log("\n" + "🎉" * 20)
        self.log("FINAL COMPLETION REPORT")
        self.log("🎉" * 20)
        
        # Time statistics
        self.log(f"⏱️ Total execution time: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        if self.stats['scraping_duration']:
            self.log(f"   📋 Step 1 (Scraping): {self.stats['scraping_duration']:.1f}s")
        if self.stats['completion_duration']:
            self.log(f"   📋 Step 2 (Completion): {self.stats['completion_duration']:.1f}s")
        if self.stats['download_duration']:
            self.log(f"   📋 Step 3 (Download): {self.stats['download_duration']:.1f}s")
        
        # Data statistics
        self.log(f"📊 Providers processed: {self.stats['total_providers']}")
        self.log(f"📊 Games found: {self.stats['total_games']}")
        self.log(f"📊 Thumbnails downloaded: {self.stats['total_thumbnails']}")
        
        # Success rate
        if self.stats['total_games'] > 0:
            success_rate = (self.stats['total_thumbnails'] / self.stats['total_games']) * 100
            self.log(f"📊 Success rate: {success_rate:.1f}%")
        
        # Errors
        if self.stats['errors']:
            self.log(f"⚠️ Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                self.log(f"   ❌ {error}")
        else:
            self.log("✅ No errors encountered!")
        
        # Output locations
        self.log(f"\n📁 Output locations:")
        self.log(f"   📋 Checkpoints: {self.checkpoints_dir}")
        self.log(f"   📋 Metadata: {self.metadata_dir}")
        self.log(f"   🎮 Game Data: {self.stake_thumbnails_dir}")
        self.log(f"   🖼️ Final Thumbnails: {self.stake_thumbnails_final_dir}")
        self.log(f"   📝 Logs: {self.logs_dir}")
        
        # Save report to JSON
        report_data = {
            'execution_summary': {
                'start_time': self.stats['start_time'].isoformat(),
                'end_time': self.stats['end_time'].isoformat(),
                'total_duration_seconds': total_duration,
                'scraping_duration': self.stats['scraping_duration'],
                'completion_duration': self.stats['completion_duration'],
                'download_duration': self.stats['download_duration']
            },
            'data_summary': {
                'total_providers': self.stats['total_providers'],
                'total_games': self.stats['total_games'],
                'total_thumbnails': self.stats['total_thumbnails'],
                'success_rate': (self.stats['total_thumbnails'] / self.stats['total_games'] * 100) if self.stats['total_games'] > 0 else 0
            },
            'errors': self.stats['errors'],
            'output_directories': {
                'checkpoints': str(self.checkpoints_dir),
                'metadata': str(self.metadata_dir),
                'game_data': str(self.stake_thumbnails_dir),
                'final_thumbnails': str(self.stake_thumbnails_final_dir),
                'logs': str(self.logs_dir)
            }
        }
        
        report_file = self.metadata_dir / "execution_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.log(f"📋 Detailed report saved: {report_file}")
    
    def run(self):
        """Run the complete pipeline"""
        try:
            # Initial setup
            self.check_dependencies()
            self.clean_directories()
            
            # Run the three-step pipeline
            success_count = 0
            
            # Step 1: Initial scraping
            if self.step_1_initial_scraping():
                success_count += 1
            
            # Step 2: Complete providers (only if step 1 succeeded or was skipped)
            if success_count > 0 or self.skip_scraping:
                if self.step_2_complete_providers():
                    success_count += 1
            
            # Step 3: Download thumbnails (only if previous steps succeeded or were skipped)
            if success_count > 1 or (self.skip_scraping and self.skip_completion):
                if self.step_3_download_thumbnails():
                    success_count += 1
            
            # Generate final report
            self.generate_final_report()
            
            # Final status
            total_steps = 3 - sum([self.skip_scraping, self.skip_completion, self.skip_download])
            if success_count == total_steps:
                self.log("🎉 All steps completed successfully!")
                return True
            else:
                self.log(f"⚠️ {success_count}/{total_steps} steps completed successfully", "WARNING")
                return False
                
        except KeyboardInterrupt:
            self.log("⏹️ Process interrupted by user", "WARNING")
            return False
        except Exception as e:
            self.log(f"💥 Fatal error: {str(e)}", "ERROR")
            return False

def main():
    """Main entry point with command line arguments"""
    parser = argparse.ArgumentParser(
        description='Stake.com Complete Game Thumbnail Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Run complete pipeline
  python main.py --clean             # Clean start (remove all existing data)
  python main.py --skip-scraping     # Skip initial scraping step
  python main.py --skip-completion   # Skip provider completion step
  python main.py --skip-download     # Skip thumbnail download step
        """
    )
    
    parser.add_argument('--clean', action='store_true',
                        help='Clean all output directories before starting')
    parser.add_argument('--skip-scraping', action='store_true',
                        help='Skip the initial scraping step')
    parser.add_argument('--skip-completion', action='store_true',
                        help='Skip the provider completion step')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip the thumbnail download step')
    
    args = parser.parse_args()
    
    # Create and run orchestrator
    orchestrator = StakeScraperOrchestrator(
        clean_start=args.clean,
        skip_scraping=args.skip_scraping,
        skip_completion=args.skip_completion,
        skip_download=args.skip_download
    )
    
    success = orchestrator.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
