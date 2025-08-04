#!/usr/bin/env python3
"""
Package script for creating GitHub releases.
Creates a zip file with all project contents except files/folders listed in .gitignore.
"""

import os
import zipfile
import fnmatch
import argparse
from pathlib import Path
from datetime import datetime

def read_gitignore(gitignore_path='.gitignore'):
    """Read .gitignore file and return list of patterns to ignore."""
    ignore_patterns = []
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    ignore_patterns.append(line)
    
    # Always ignore the releases folder and git files
    ignore_patterns.extend([
        'releases/*',
        'releases/',
        '.git/*',
        '.git/',
        '*.zip'
    ])
    
    return ignore_patterns

def should_ignore(file_path, ignore_patterns):
    """Check if a file should be ignored based on .gitignore patterns."""
    # Convert to forward slashes for consistent pattern matching
    normalized_path = file_path.replace('\\', '/')
    
    for pattern in ignore_patterns:
        # Handle directory patterns
        if pattern.endswith('/'):
            if normalized_path.startswith(pattern) or normalized_path + '/' == pattern:
                return True
        # Handle glob patterns
        elif fnmatch.fnmatch(normalized_path, pattern):
            return True
        # Handle patterns with wildcards in directories
        elif '/' in pattern and fnmatch.fnmatch(normalized_path, pattern):
            return True
        # Handle simple filename patterns
        elif '/' not in pattern and fnmatch.fnmatch(os.path.basename(normalized_path), pattern):
            return True
    
    return False

def create_release_package(version=None, output_dir='releases'):
    """Create a zip package for release."""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename
    if version:
        zip_filename = f'oak-tower-watcher-{version}.zip'
    else:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        zip_filename = f'oak-tower-watcher-{timestamp}.zip'
    
    zip_path = os.path.join(output_dir, zip_filename)
    
    # Read .gitignore patterns
    ignore_patterns = read_gitignore()
    
    print(f"Creating package: {zip_path}")
    print(f"Ignoring patterns: {ignore_patterns}")
    
    # Create zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through all files in current directory
        for root, dirs, files in os.walk('.'):
            # Remove leading './' or '.\'
            root_clean = root[2:] if root.startswith('./') or root.startswith('.\\') else root
            if root_clean == '.':
                root_clean = ''
            
            # Check if current directory should be ignored
            if root_clean and should_ignore(root_clean, ignore_patterns):
                dirs.clear()  # Don't recurse into ignored directories
                continue
            
            # Filter out ignored directories for next iteration
            dirs[:] = [d for d in dirs if not should_ignore(
                os.path.join(root_clean, d) if root_clean else d, ignore_patterns
            )]
            
            # Add files that aren't ignored
            for file in files:
                file_path = os.path.join(root_clean, file) if root_clean else file
                
                if not should_ignore(file_path, ignore_patterns):
                    full_path = os.path.join(root, file)
                    print(f"Adding: {file_path}")
                    zipf.write(full_path, file_path)
    
    print(f"\nPackage created successfully: {zip_path}")
    print(f"Package size: {os.path.getsize(zip_path)} bytes")
    
    return zip_path

def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(description='Package Oak Tower Watcher for release')
    parser.add_argument('-v', '--version', help='Version string for the package filename')
    parser.add_argument('-o', '--output', default='releases', help='Output directory (default: releases)')
    
    args = parser.parse_args()
    
    try:
        zip_path = create_release_package(args.version, args.output)
        print(f"\n✅ Release package ready: {zip_path}")
    except Exception as e:
        print(f"❌ Error creating package: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())