#!/usr/bin/env python3
r"""
Configuration management module for VATSIM Tower Monitor
Handles loading and saving of configuration settings.

Callsign Configuration:
- Uses regex patterns to match controller callsigns
- Each category (main_facility, supporting_above, supporting_below) contains a list of regex patterns
- Patterns are case-insensitive and use full string matching (^ and $ anchors)
- Examples:
  - ^OAK_(?:\d+_)?TWR$ matches OAK_TWR, OAK_1_TWR, OAK_2_TWR, etc.
  - ^OAK_\d+_CTR$ matches OAK_36_CTR, OAK_62_CTR, etc.
"""

import json
import os
import logging


def load_config():
    """Load configuration from config.json file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    default_config = {
        "airport": {
            "code": "KOAK",
            "name": "Oakland International Airport",
            "display_name": "Oakland Tower",
        },
        "monitoring": {"check_interval": 30},
        "callsigns": {
            "main_facility": [r"^OAK_(?:\d+_)?TWR$"],
            "supporting_above": [r"^NCT_APP$", r"^OAK_\d+_CTR$"],
            "supporting_below": [r"^OAK_(?:\d+_)?GND$", r"^OAK_(?:\d+_)?DEL$"],
        },
        "api": {
            "vatsim_url": "https://data.vatsim.net/v3/vatsim-data.json",
            "roster_url": "https://oakartcc.org/about/roster",
        },
        "notifications": {
            "sound_enabled": True,
            "sound_file": "ding.mp3",
            "toast_duration": 3000,
        },
        "colors": {
            "notifications": {
                "main_facility_and_supporting_above_online": "rgb(75, 0, 130)",
                "main_facility_online": "rgb(0, 100, 0)",
                "supporting_above_online": "rgb(184, 134, 11)",
                "all_offline": "rgb(139, 0, 0)",
                "error": "rgb(64, 64, 64)",
            },
        },
    }

    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logging.info(f"Loaded configuration from {config_path}")
                return config
        else:
            logging.warning(f"Config file not found at {config_path}, using defaults")
            # Create default config file
            save_config(default_config)
            return default_config
    except Exception as e:
        logging.error(f"Error loading config file: {e}, using defaults")
        return default_config


def save_config(config):
    """Save configuration to config.json file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            logging.info(f"Saved configuration to {config_path}")
    except Exception as e:
        logging.error(f"Error saving config file: {e}")
