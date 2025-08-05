#!/usr/bin/env python3
"""
Create deployment package for headless VATSIM monitor
This script creates a deployment package maintaining the organized directory structure.
"""

import os
import shutil
import sys
from pathlib import Path

def create_deployment_package():
    """Create deployment package maintaining the organized directory structure"""
    
    # Get the project root directory (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Create deployment package directory
    package_dir = project_root / "deployment_package"
    
    # Remove existing package directory if it exists
    if package_dir.exists():
        shutil.rmtree(package_dir)
    
    package_dir.mkdir()
    
    print(f"Creating deployment package in: {package_dir}")
    
    # Create directory structure
    (package_dir / "src").mkdir()
    (package_dir / "config").mkdir()
    (package_dir / "logs").mkdir()
    
    # Files to copy with their source and destination paths (maintaining structure)
    files_to_copy = [
        # Entry point (from root)
        ("headless_monitor.py", "headless_monitor.py"),
        
        # Supporting modules (from src/) - maintain in src/
        ("src/headless_worker.py", "src/headless_worker.py"),
        ("src/notification_manager.py", "src/notification_manager.py"),
        ("src/utils.py", "src/utils.py"),
        ("src/pushover_service.py", "src/pushover_service.py"),
        
        # Configuration files (from config/) - maintain in config/
        ("config/config.py", "config/config.py"),
        ("requirements_headless.txt", "requirements_headless.txt"),
        ("config/vatsim-monitor.service", "config/vatsim-monitor.service"),
        
        # User configuration (from root)
        ("config.json", "config.json"),
    ]
    
    # Copy files maintaining directory structure
    copied_files = []
    missing_files = []
    
    for src_path, dst_path in files_to_copy:
        src_file = project_root / src_path
        dst_file = package_dir / dst_path
        
        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            copied_files.append(dst_path)
            print(f"✓ Copied: {src_path} -> {dst_path}")
        else:
            missing_files.append(src_path)
            print(f"✗ Missing: {src_path}")
    
    print(f"\nDeployment package created successfully!")
    print(f"Location: {package_dir}")
    print(f"Files copied: {len(copied_files)}")
    
    if missing_files:
        print(f"\nWarning: {len(missing_files)} files were missing:")
        for file in missing_files:
            print(f"  - {file}")
    
    print(f"\nDirectory structure maintained - no import path changes needed!")
    print(f"\nTo deploy to your server:")
    print(f"1. Upload the entire deployment_package directory structure to your server")
    print(f"2. Follow the deployment guide in docs/DEPLOYMENT_GUIDE.md")
    
    return len(missing_files) == 0

if __name__ == "__main__":
    success = create_deployment_package()
    sys.exit(0 if success else 1)