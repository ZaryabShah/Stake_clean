#!/usr/bin/env python3
"""
Test script to verify the Stake scraper setup and dependencies
"""

import sys
import subprocess
import importlib
from pathlib import Path

def test_python_packages():
    """Test if all required Python packages are available"""
    print("🐍 Testing Python packages...")
    
    required_packages = [
        ('requests', 'HTTP library'),
        ('PIL', 'Image processing (Pillow)'),
        ('bs4', 'BeautifulSoup4 HTML parsing'),
        ('aiohttp', 'Async HTTP client'),
    ]
    
    missing_packages = []
    
    for package_name, description in required_packages:
        try:
            importlib.import_module(package_name)
            print(f"   ✅ {description}")
        except ImportError:
            print(f"   ❌ {description} - MISSING")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n💡 Install missing packages:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def test_node_js():
    """Test if Node.js is available"""
    print("\n🟨 Testing Node.js...")
    
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ Node.js {version}")
            return True
        else:
            print(f"   ❌ Node.js command failed")
            return False
    except FileNotFoundError:
        print(f"   ❌ Node.js not found")
        print(f"   💡 Install Node.js from: https://nodejs.org/")
        return False

def test_project_files():
    """Test if all required project files exist"""
    print("\n📁 Testing project files...")
    
    project_root = Path(__file__).parent
    required_files = [
        ('main.py', 'Main orchestrator script'),
        ('robust_stake_scraper.py', 'Initial scraping script'),
        ('complete_all_providers_parallel.js', 'Provider completion script'),
        ('thumbnail_downloader_fixed.py', 'Thumbnail downloader'),
        ('hardcoded_providers.py', 'Provider definitions'),
        ('requirements.txt', 'Python dependencies'),
        ('README.md', 'Documentation')
    ]
    
    missing_files = []
    
    for filename, description in required_files:
        file_path = project_root / filename
        if file_path.exists():
            print(f"   ✅ {description}")
        else:
            print(f"   ❌ {description} - MISSING")
            missing_files.append(filename)
    
    if missing_files:
        print(f"\n💡 Missing files: {', '.join(missing_files)}")
        return False
    
    return True

def test_directory_creation():
    """Test if we can create required directories"""
    print("\n📂 Testing directory creation...")
    
    project_root = Path(__file__).parent
    test_directories = [
        'checkpoints',
        'metadata', 
        'stake_thumbnails',
        'stake_thumbnails_final',
        'logs'
    ]
    
    for dir_name in test_directories:
        try:
            dir_path = project_root / dir_name
            dir_path.mkdir(exist_ok=True)
            print(f"   ✅ {dir_name}/ directory")
        except Exception as e:
            print(f"   ❌ {dir_name}/ directory - ERROR: {str(e)}")
            return False
    
    return True

def main():
    """Run all tests"""
    print("🧪 Stake Scraper Setup Test")
    print("=" * 40)
    
    tests = [
        ("Python Packages", test_python_packages),
        ("Node.js", test_node_js),
        ("Project Files", test_project_files),
        ("Directory Creation", test_directory_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_function in tests:
        try:
            if test_function():
                passed += 1
            else:
                print(f"\n⚠️ {test_name} test failed")
        except Exception as e:
            print(f"\n💥 {test_name} test crashed: {str(e)}")
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Ready to run the scraper.")
        print("\n🚀 Next steps:")
        print("   python main.py --help    # See all options")
        print("   python main.py           # Run complete pipeline")
        print("   python main.py --clean   # Run with clean start")
    else:
        print("❌ Some tests failed. Please fix the issues above before running the scraper.")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
