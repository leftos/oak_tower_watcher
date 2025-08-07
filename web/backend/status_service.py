#!/usr/bin/env python3
"""
VATSIM Status Service - handles status API operations
"""

import json
import logging
import os
import sys
from datetime import datetime

# Import shared components using new structure
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.config import load_config
from shared.vatsim_core import VATSIMCore
from shared.utils import load_artcc_roster, get_controller_name, get_facility_display_name, extract_facility_name_from_callsign

# Import web models for user configuration support
try:
    from .models import User, UserSettings
    WEB_MODELS_AVAILABLE = True
except ImportError:
    WEB_MODELS_AVAILABLE = False
    logging.warning("Web models not available - user configurations disabled")

class StatusAPI:
    def __init__(self):
        self.config = load_config()
        
        # Load ARTCC roster for controller names
        roster_url = self.config.get("api", {}).get(
            "roster_url", "https://oakartcc.org/about/roster"
        )
        self.controller_names = load_artcc_roster(roster_url)
        
        # Create a core VATSIM client instance with default config
        self.vatsim_core = VATSIMCore(self.config)
        
        logging.info("Status API initialized")
    
    def _get_user_facility_patterns(self, user_id):
        """Get user-specific facility patterns if available"""
        if not WEB_MODELS_AVAILABLE or not user_id:
            return None
        
        try:
            # Import here to avoid circular imports
            from flask import current_app
            
            with current_app.app_context():
                user = User.query.get(user_id)
                if not user:
                    return None
                
                settings = user.get_service_settings('oak_tower_watcher')
                if not settings:
                    return None
                
                patterns = settings.get_all_facility_patterns()
                
                # Only return patterns if at least one type has patterns
                if any(patterns.values()):
                    return patterns
                
                return None
                
        except Exception as e:
            logging.error(f"Error getting user facility patterns for user {user_id}: {str(e)}")
            return None
    
    def _create_user_vatsim_core(self, user_patterns):
        """Create a VATSIMCore instance with user-specific patterns"""
        try:
            # Create a modified config with user patterns
            user_config = self.config.copy()
            user_config['callsigns'] = user_patterns
            
            # Create VATSIMCore instance with user config
            return VATSIMCore(user_config)
            
        except Exception as e:
            logging.error(f"Error creating user VATSIM core: {str(e)}")
            return self.vatsim_core  # Fallback to default

    def get_current_status(self, user_id=None):
        """Get current VATSIM status, optionally using user-specific configuration"""
        try:
            # Check if user has custom facility patterns
            user_patterns = None
            vatsim_core = self.vatsim_core  # Default
            
            if user_id:
                user_patterns = self._get_user_facility_patterns(user_id)
                if user_patterns:
                    vatsim_core = self._create_user_vatsim_core(user_patterns)
                    logging.debug(f"Using custom facility patterns for user {user_id}")
            
            # Use the appropriate VATSIM client to check status
            result = vatsim_core.check_status()
            
            if not result["success"]:
                return {
                    "error": result.get("error", "Failed to query VATSIM API"),
                    "status": "error",
                    "timestamp": result["timestamp"]
                }
            
            # Format controller data
            def format_controllers(controllers):
                if not controllers:
                    return []
                
                formatted = []
                for controller in controllers:
                    formatted.append({
                        "callsign": controller.get("callsign", "Unknown"),
                        "name": get_controller_name(controller, self.controller_names),
                        "frequency": controller.get("frequency", "Unknown"),
                        "cid": controller.get("cid", "Unknown"),
                        "logon_time": controller.get("logon_time", "Unknown"),
                        "server": controller.get("server", "Unknown"),
                        "rating": controller.get("rating", 0)
                    })
                return formatted
            
            # Get dynamic facility name based on current status and controllers
            facility_name = get_facility_display_name(
                result["status"],
                result["main_controllers"],
                result["supporting_above"],
                "Main Facility"
            )
            
            response = {
                "status": result["status"],
                "facility_name": facility_name,
                "timestamp": result["timestamp"],
                "main_controllers": format_controllers(result["main_controllers"]),
                "supporting_above": format_controllers(result["supporting_above"]),
                "supporting_below": format_controllers(result["supporting_below"]),
                "config": {
                    "check_interval": self.config.get("monitoring", {}).get("check_interval", 30)
                }
            }
            
            # Add user configuration info if custom patterns were used
            if user_patterns:
                response["using_user_config"] = True
                response["facility_patterns"] = user_patterns
            else:
                response["using_user_config"] = False
            
            return response
            
        except Exception as e:
            logging.error(f"Error getting status: {e}")
            return {
                "error": str(e),
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }

# Create global status API instance
status_api = StatusAPI()