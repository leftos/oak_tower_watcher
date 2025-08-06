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
from shared.utils import load_artcc_roster, get_controller_name

class StatusAPI:
    def __init__(self):
        self.config = load_config()
        self.airport_config = self.config.get("airport", {})
        self.airport_code = self.airport_config.get("code", "KOAK")
        self.display_name = self.airport_config.get("display_name", "Oakland Tower")
        
        # Load ARTCC roster for controller names
        roster_url = self.config.get("api", {}).get(
            "roster_url", "https://oakartcc.org/about/roster"
        )
        self.controller_names = load_artcc_roster(roster_url)
        
        # Create a core VATSIM client instance
        self.vatsim_core = VATSIMCore(self.config)
        
        logging.info(f"Status API initialized for {self.display_name}")

    def get_current_status(self):
        """Get current VATSIM status"""
        try:
            # Use the core VATSIM client to check status
            result = self.vatsim_core.check_status()
            
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
            
            return {
                "status": result["status"],
                "airport_code": self.airport_code,
                "display_name": self.display_name,
                "timestamp": result["timestamp"],
                "main_controllers": format_controllers(result["main_controllers"]),
                "supporting_above": format_controllers(result["supporting_above"]),
                "supporting_below": format_controllers(result["supporting_below"]),
                "config": {
                    "check_interval": self.config.get("monitoring", {}).get("check_interval", 30),
                    "airport_name": self.airport_config.get("name", "Oakland International Airport")
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting status: {e}")
            return {
                "error": str(e),
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }

# Create global status API instance
status_api = StatusAPI()