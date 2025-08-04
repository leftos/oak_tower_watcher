#!/usr/bin/env python3
"""
Auto-updater module for VATSIM Tower Monitor
Handles checking for and downloading updates from GitHub.
"""

import os
import json
import logging
import tempfile
import zipfile
import shutil
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class GitHubUpdater:
    """Handles auto-updating from GitHub releases"""
    
    def __init__(self, repo_name, current_version=None):
        """
        Initialize the updater
        
        Args:
            repo_name (str): GitHub repository in format "owner/repo"
            current_version (str): Current version string (optional)
        """
        self.repo_name = repo_name
        self.current_version = current_version
        self.github_api_base = "https://api.github.com"
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
    def get_latest_release(self):
        """
        Get information about the latest release from GitHub API
        
        Returns:
            dict: Release information or None if error
        """
        try:
            url = f"{self.github_api_base}/repos/{self.repo_name}/releases/latest"
            request = Request(url)
            request.add_header('User-Agent', 'VATSIM-Tower-Monitor-Updater/1.0')
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data
                
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logging.error(f"Failed to fetch latest release info: {e}")
            return None
    
    def is_newer_version(self, latest_version):
        """
        Compare versions to determine if update is needed
        
        Args:
            latest_version (str): Version string from GitHub
            
        Returns:
            bool: True if latest version is newer
        """
        if not self.current_version:
            return True  # Always update if no current version
            
        # Simple version comparison - assumes semantic versioning
        try:
            current_parts = [int(x) for x in self.current_version.lstrip('v').split('.')]
            latest_parts = [int(x) for x in latest_version.lstrip('v').split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            
            return latest_parts > current_parts
            
        except (ValueError, AttributeError):
            # If version parsing fails, assume update is needed
            logging.warning(f"Could not parse versions: current={self.current_version}, latest={latest_version}")
            return True
    
    def download_file(self, url, local_path):
        """
        Download a file from URL to local path
        
        Args:
            url (str): URL to download from
            local_path (str): Local file path to save to
            
        Returns:
            bool: True if successful
        """
        try:
            request = Request(url)
            request.add_header('User-Agent', 'VATSIM-Tower-Monitor-Updater/1.0')
            
            with urlopen(request, timeout=30) as response:
                with open(local_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
                    
            logging.info(f"Downloaded {url} to {local_path}")
            return True
            
        except (URLError, HTTPError, IOError) as e:
            logging.error(f"Failed to download {url}: {e}")
            return False
    
    def extract_update(self, zip_path, extract_to):
        """
        Extract update zip file
        
        Args:
            zip_path (str): Path to zip file
            extract_to (str): Directory to extract to
            
        Returns:
            bool: True if successful
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logging.info(f"Extracted {zip_path} to {extract_to}")
            return True
            
        except (zipfile.BadZipFile, IOError) as e:
            logging.error(f"Failed to extract {zip_path}: {e}")
            return False
    
    def backup_current_files(self):
        """
        Create backup of current files
        
        Returns:
            str: Path to backup directory or None if failed
        """
        try:
            backup_dir = os.path.join(self.script_dir, f"backup_{int(os.path.getmtime(self.script_dir))}")
            
            # Files to backup
            files_to_backup = [
                'main.py', 'config.py', 'vatsim_monitor.py', 'vatsim_worker.py',
                'gui_components.py', 'utils.py', 'requirements.txt'
            ]
            
            os.makedirs(backup_dir, exist_ok=True)
            
            for file_name in files_to_backup:
                src_path = os.path.join(self.script_dir, file_name)
                if os.path.exists(src_path):
                    dst_path = os.path.join(backup_dir, file_name)
                    shutil.copy2(src_path, dst_path)
            
            logging.info(f"Created backup at {backup_dir}")
            return backup_dir
            
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup: {e}")
            return None
    
    def apply_update(self, update_dir):
        """
        Apply update by copying new files over current ones
        
        Args:
            update_dir (str): Directory containing update files
            
        Returns:
            bool: True if successful
        """
        try:
            # Files to update
            files_to_update = [
                'main.py', 'config.py', 'vatsim_monitor.py', 'vatsim_worker.py',
                'gui_components.py', 'utils.py', 'requirements.txt', 'updater.py'
            ]
            
            for file_name in files_to_update:
                src_path = os.path.join(update_dir, file_name)
                dst_path = os.path.join(self.script_dir, file_name)
                
                if os.path.exists(src_path):
                    shutil.copy2(src_path, dst_path)
                    logging.info(f"Updated {file_name}")
            
            return True
            
        except (IOError, OSError) as e:
            logging.error(f"Failed to apply update: {e}")
            return False
    
    def check_and_update(self):
        """
        Check for updates and apply if available
        
        Returns:
            tuple: (success: bool, message: str, updated: bool)
        """
        logging.info("Checking for updates...")
        
        # Get latest release info
        release_info = self.get_latest_release()
        if not release_info:
            return False, "Failed to check for updates", False
        
        latest_version = release_info.get('tag_name', '')
        if not latest_version:
            return False, "No version information found", False
        
        # Check if update is needed
        if not self.is_newer_version(latest_version):
            logging.info(f"Already up to date (current: {self.current_version}, latest: {latest_version})")
            return True, f"Already up to date ({latest_version})", False
        
        logging.info(f"Update available: {self.current_version} -> {latest_version}")
        
        # Find download URL for source code
        download_url = None
        for asset in release_info.get('assets', []):
            if asset['name'].endswith('.zip') and 'source' not in asset['name'].lower():
                download_url = asset['browser_download_url']
                break
        
        # Fallback to source code zip
        if not download_url:
            download_url = release_info.get('zipball_url')
        
        if not download_url:
            return False, "No download URL found", False
        
        # Create temporary directory for update
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'update.zip')
            extract_dir = os.path.join(temp_dir, 'extracted')
            
            # Download update
            if not self.download_file(download_url, zip_path):
                return False, "Failed to download update", False
            
            # Extract update
            if not self.extract_update(zip_path, extract_dir):
                return False, "Failed to extract update", False
            
            # Find the actual source directory (GitHub zips have a root folder)
            extracted_contents = os.listdir(extract_dir)
            if len(extracted_contents) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_contents[0])):
                source_dir = os.path.join(extract_dir, extracted_contents[0])
            else:
                source_dir = extract_dir
            
            # Create backup
            backup_dir = self.backup_current_files()
            if not backup_dir:
                logging.warning("Failed to create backup, continuing anyway...")
            
            # Apply update
            if not self.apply_update(source_dir):
                return False, "Failed to apply update", False
        
        logging.info(f"Successfully updated to version {latest_version}")
        return True, f"Updated to version {latest_version}", True


def check_for_updates(config):
    """
    Check for updates based on configuration
    
    Args:
        config (dict): Configuration dictionary
        
    Returns:
        tuple: (success: bool, message: str, updated: bool)
    """
    auto_update_config = config.get('auto_update', {})
    
    if not auto_update_config.get('enabled', True):
        return True, "Auto-update disabled", False
    
    repo_name = auto_update_config.get('github_repo', 'Leftos/oak_tower_watcher')
    
    # Try to get current version from git or file
    current_version = get_current_version()
    
    updater = GitHubUpdater(repo_name, current_version)
    return updater.check_and_update()


def get_current_version():
    """
    Get current version from git or version file
    
    Returns:
        str: Current version or None
    """
    try:
        # Try to get version from git
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    # Try to read from version file
    version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r') as f:
                return f.read().strip()
        except IOError:
            pass
    
    return None


if __name__ == "__main__":
    # Test the updater
    logging.basicConfig(level=logging.INFO)
    
    config = {
        'auto_update': {
            'enabled': True,
            'github_repo': 'Leftos/oak_tower_watcher'
        }
    }
    
    success, message, updated = check_for_updates(config)
    print(f"Update check: {message} (Success: {success}, Updated: {updated})")