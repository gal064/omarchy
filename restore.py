#!/usr/bin/env python3

"""
Simple restore script for Omarchy customizations
This script only restores .original backup files created by customize.py
"""

import shutil
import sys
from pathlib import Path


def restore_file_from_backup(file_path):
    """Restore a file from its .original backup"""
    file_path = Path(file_path)
    backup_path = file_path.with_suffix(file_path.suffix + ".original")
    
    if not backup_path.exists():
        print(f"- No backup found for {file_path}")
        return False
    
    try:
        shutil.copy2(backup_path, file_path)
        print(f"✓ Restored {file_path} from backup")
        return True
    except Exception as e:
        print(f"! Failed to restore {file_path}: {e}")
        return False


def find_and_restore_backups():
    """Find all .original backup files and restore them"""
    print("Searching for backup files...")
    
    home = Path.home()
    restored_count = 0
    
    # Common locations where backups might be created
    search_paths = [
        home / ".bashrc.original",
        home / ".config/hypr/hyprland.conf.original",
        home / ".config/hypr/hypridle.conf.original",
        home / ".config/waybar/config.original",
        home / ".config/waybar/style.css.original",
        home / ".config/toshy/toshy_config.py.original",
        Path("/etc/keyd/default.conf.original")
    ]
    
    # Also search recursively in common config directories
    config_dirs = [
        home / ".config",
        home / ".local/share"
    ]
    
    for config_dir in config_dirs:
        if config_dir.exists():
            for backup_file in config_dir.rglob("*.original"):
                search_paths.append(backup_file)
    
    # Remove duplicates
    search_paths = list(set(search_paths))
    
    for backup_path in search_paths:
        if backup_path.exists():
            original_path = backup_path.with_suffix('')
            if original_path.suffix == '.original':
                # Handle cases where the backup has double extension
                original_path = backup_path.parent / backup_path.stem
            
            try:
                shutil.copy2(backup_path, original_path)
                print(f"✓ Restored {original_path} from {backup_path}")
                restored_count += 1
            except Exception as e:
                print(f"! Failed to restore {original_path}: {e}")
    
    if restored_count == 0:
        print("- No backup files found to restore")
    else:
        print(f"✓ Restored {restored_count} files from backups")


def main():
    """Main restoration function"""
    print("Restoring files from .original backups...")
    print("=" * 40)
    
    try:
        find_and_restore_backups()
        print("=" * 40)
        print("✓ Backup restoration complete!")
        
    except KeyboardInterrupt:
        print("\n! Restoration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n! Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()