#!/usr/bin/env python3
"""
Web-Specific VATSIM Monitoring Service
Monitors all facilities that registered users care about, not just the default Oakland ones.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import shared components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.config import load_config
from shared.vatsim_core import VATSIMCore
from shared.notification_manager import NotificationManager
from shared.database_interface import DatabaseInterface
from shared.utils import load_artcc_roster


class WebMonitoringService:
    """
    Web-specific monitoring service that monitors all facilities users care about
    """
    
    def __init__(self):
        self.config = load_config()
        self.db_interface = DatabaseInterface()
        self.notification_manager = None
        self.vatsim_core = None
        
        # Threading control
        self.running = False
        self.monitor_thread = None
        self.check_interval = self.config.get("monitoring", {}).get("check_interval", 60)
        
        # Previous status tracking for overall system
        self.previous_status = "all_offline"
        self.previous_controllers = {
            'main': [],
            'supporting_above': [],
            'supporting_below': []
        }
        
        # Cached status data for UI consumption
        self._cached_status = None
        self._cache_lock = threading.Lock()
        self.last_cache_update = None
        
        # Load ARTCC roster for controller names
        roster_url = self.config.get("api", {}).get(
            "roster_url", "https://oakartcc.org/about/roster"
        )
        self.controller_names = load_artcc_roster(roster_url)
        
        # Initialize notification manager
        self.notification_manager = NotificationManager(self.config, self.controller_names)
        
        logging.info("Web monitoring service initialized")
    
    def get_aggregated_config(self) -> Optional[Dict[str, Any]]:
        """
        Get configuration with aggregated facility patterns from all users
        
        Returns:
            Config dictionary with aggregated patterns or None if no users found
        """
        if not self.db_interface.enabled:
            logging.warning("Database interface not available - falling back to default config")
            return None
        
        try:
            # Get all unique facility patterns from all users
            aggregated_patterns = self.db_interface.get_all_user_facility_patterns()
            
            # If no custom patterns found, return None to use default config
            total_patterns = sum(len(patterns) for patterns in aggregated_patterns.values())
            if total_patterns == 0:
                logging.info("No custom user facility patterns found - using default config")
                return None
            
            # Create config with aggregated patterns
            aggregated_config = self.config.copy()
            
            # Use aggregated user patterns directly - no merging with defaults
            # Default patterns are already included by get_all_user_facility_patterns() if no user patterns exist
            aggregated_config['callsigns'] = aggregated_patterns
            
            total_patterns = sum(len(patterns) for patterns in aggregated_patterns.values())
            logging.info(f"Using aggregated config with {total_patterns} facility patterns (user patterns only)")
            
            return aggregated_config
            
        except Exception as e:
            logging.error(f"Error creating aggregated config: {e}")
            return None
    
    def _get_facility_display_names(self) -> Dict[str, str]:
        """
        Extract representative facility names from configuration patterns
        
        Returns:
            Dictionary with facility type as key and representative name as value
        """
        try:
            # Get the effective config (aggregated if available, otherwise default)
            config = self.get_aggregated_config() or self.config
            callsigns = config.get('callsigns', {})
            
            facility_names = {}
            
            # Extract representative names from regex patterns
            for facility_type in ['main_facility', 'supporting_above', 'supporting_below']:
                patterns = callsigns.get(facility_type, [])
                if patterns:
                    # Try to extract a clean callsign from the first pattern
                    pattern = patterns[0]
                    
                    # Extract facility name from regex pattern
                    import re
                    
                    # Check if it's already a simple callsign (no regex special characters)
                    # If it only contains letters, numbers, and underscores, treat it as an exact callsign
                    if re.match(r'^[A-Z0-9_]+$', pattern) and not any(char in pattern for char in ['^', '$', '\\', '(', ')', '?', '+', '*', '[', ']', '{', '}']):
                        # It's already a plain callsign like "SAN_TWR", "SCT_APP", "SAN_GND", "OAK_12_TWR", "OAK_N_TWR"
                        facility_names[facility_type] = pattern
                        logging.debug(f"Using exact callsign: {pattern}")
                    else:
                        # Remove regex anchors and escape characters, but preserve the core callsign
                        clean_pattern = pattern.replace('^', '').replace('$', '')
                        
                        # Handle simple patterns first (like ^SAN_TWR$, ^SCT_APP$, ^SAN_GND$)
                        simple_match = re.search(r'^([A-Z]{3,4}_[A-Z]{2,4})$', clean_pattern)
                        if simple_match:
                            facility_names[facility_type] = simple_match.group(1)
                            logging.debug(f"Extracted simple facility name: {simple_match.group(1)} from pattern: {pattern}")
                        else:
                            # Handle more complex patterns
                            clean_pattern = clean_pattern.replace('\\d+', '').replace('\\', '').replace('(?:', '').replace(')?', '').replace('_+', '_')
                            # Clean up consecutive underscores and trim
                            clean_pattern = re.sub(r'_+', '_', clean_pattern).strip('_')
                            
                            # Look for common callsign patterns like XXX_TWR, XXX_APP, XXX_GND, etc.
                            callsign_match = re.search(r'([A-Z]{3,4})_([A-Z]{2,4})', clean_pattern)
                            if callsign_match:
                                facility_names[facility_type] = f"{callsign_match.group(1)}_{callsign_match.group(2)}"
                                logging.debug(f"Extracted complex facility name: {callsign_match.group(1)}_{callsign_match.group(2)} from pattern: {pattern}")
                            else:
                                # Try to find any combination of letters and underscores
                                letters_match = re.search(r'([A-Z_]+)', clean_pattern)
                                if letters_match:
                                    # Clean up the matched pattern
                                    name = letters_match.group(1).strip('_')
                                    # If it doesn't have an underscore, it's probably incomplete
                                    if '_' not in name:
                                        # Try common facility type mappings based on context
                                        if facility_type == 'main_facility':
                                            name += '_TWR'
                                        elif facility_type == 'supporting_above':
                                            name += '_APP'
                                        elif facility_type == 'supporting_below':
                                            name += '_GND'
                                    facility_names[facility_type] = name
                                    logging.debug(f"Extracted fallback facility name: {name} from pattern: {pattern}")
                                else:
                                    facility_names[facility_type] = f"{facility_type.replace('_', ' ').title()}"
                                    logging.debug(f"Using default facility name for {facility_type}")
                else:
                    facility_names[facility_type] = f"{facility_type.replace('_', ' ').title()}"
                    
            logging.debug(f"Extracted facility names: {facility_names}")
            return facility_names
            
        except Exception as e:
            logging.error(f"Error extracting facility names: {e}")
            return {
                'main_facility': 'Main Facility',
                'supporting_above': 'Supporting Above',
                'supporting_below': 'Supporting Below'
            }
    
    def check_status_with_aggregated_config(self) -> Dict[str, Any]:
        """
        Check VATSIM status using aggregated facility patterns from all users
        
        Returns:
            Status result dictionary
        """
        try:
            # Get aggregated configuration
            aggregated_config = self.get_aggregated_config()
            
            if aggregated_config:
                # Create VATSIMCore with aggregated patterns
                vatsim_core = VATSIMCore(aggregated_config)
                logging.debug("Using aggregated facility patterns for monitoring")
            else:
                # Fall back to default config
                vatsim_core = VATSIMCore(self.config)
                logging.debug("Using default facility patterns for monitoring")
            
            # Check current status
            result = vatsim_core.check_status()
            
            if result['success']:
                logging.debug(f"Status check successful: {result['status']}")
            else:
                logging.warning(f"Status check failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logging.error(f"Error checking status with aggregated config: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error',
                'main_controllers': [],
                'supporting_above': [],
                'supporting_below': [],
                'timestamp': datetime.now().isoformat()
            }
    
    def has_status_changed(self, current_result: Dict[str, Any]) -> bool:
        """
        Check if the overall monitored status has changed
        
        Args:
            current_result: Current status check result
            
        Returns:
            True if status has changed, False otherwise
        """
        if not current_result['success']:
            return False
        
        current_status = current_result['status']
        current_main = current_result.get('main_controllers', [])
        current_above = current_result.get('supporting_above', [])
        current_below = current_result.get('supporting_below', [])
        
        # Check if status changed
        if current_status != self.previous_status:
            logging.info(f"Overall status changed from {self.previous_status} to {current_status}")
            return True
        
        # Check if controller lists changed (simplified check)
        def get_callsigns(controllers):
            return sorted([c.get('callsign', '') for c in controllers])
        
        if (get_callsigns(current_main) != get_callsigns(self.previous_controllers['main']) or
            get_callsigns(current_above) != get_callsigns(self.previous_controllers['supporting_above']) or
            get_callsigns(current_below) != get_callsigns(self.previous_controllers['supporting_below'])):
            logging.info("Controller lists have changed")
            return True
        
        return False
    
    def update_previous_status(self, current_result: Dict[str, Any]):
        """
        Update stored previous status
        
        Args:
            current_result: Current status check result
        """
        if current_result['success']:
            self.previous_status = current_result['status']
            self.previous_controllers = {
                'main': current_result.get('main_controllers', []),
                'supporting_above': current_result.get('supporting_above', []),
                'supporting_below': current_result.get('supporting_below', [])
            }
    
    def update_cached_status(self, status_result: Dict[str, Any]):
        """
        Update cached status data for UI consumption
        
        Args:
            status_result: Latest status check result
        """
        try:
            with self._cache_lock:
                # Get configured facility names for display
                facility_names = self._get_facility_display_names()
                
                self._cached_status = {
                    'status': status_result.get('status', 'error'),
                    'facility_name': 'Monitored Facilities',  # Generic name for aggregated monitoring
                    'main_controllers': status_result.get('main_controllers', []),
                    'supporting_above': status_result.get('supporting_above', []),
                    'supporting_below': status_result.get('supporting_below', []),
                    'timestamp': status_result.get('timestamp', datetime.now().isoformat()),
                    'success': status_result.get('success', False),
                    'error': status_result.get('error'),
                    'config': {
                        'check_interval': self.check_interval
                    },
                    'monitoring_service': {
                        'using_aggregated_config': self.get_aggregated_config() is not None,
                        'running': self.is_running()
                    },
                    'facility_names': facility_names
                }
                self.last_cache_update = datetime.now()
                
                logging.debug(f"Updated cached status: {status_result.get('status', 'unknown')}")
                
        except Exception as e:
            logging.error(f"Error updating cached status: {e}")
    
    def get_cached_status(self) -> Optional[Dict[str, Any]]:
        """
        Get cached status data for UI consumption
        
        Returns:
            Cached status dictionary or None if no data available
        """
        try:
            with self._cache_lock:
                if self._cached_status is None:
                    return None
                
                # Add cache age information
                cached_data = self._cached_status.copy()
                if self.last_cache_update:
                    cache_age = datetime.now() - self.last_cache_update
                    cached_data['cache_age_seconds'] = int(cache_age.total_seconds())
                    cached_data['last_updated'] = self.last_cache_update.isoformat()
                
                return cached_data
                
        except Exception as e:
            logging.error(f"Error getting cached status: {e}")
            return None
    
    def get_user_filtered_status(self, user_facility_patterns: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
        """
        Get cached status data filtered by user's facility patterns
        
        Args:
            user_facility_patterns: Dictionary with keys 'main_facility', 'supporting_above', 'supporting_below'
                                  and values as lists of regex patterns
        
        Returns:
            Filtered status dictionary or None if no cached data available
        """
        try:
            # Get the full cached status first
            cached_data = self.get_cached_status()
            if cached_data is None:
                return None
            
            # If no user patterns provided, return unfiltered data
            if not user_facility_patterns or not any(user_facility_patterns.values()):
                cached_data['using_user_config'] = False
                return cached_data
            
            logging.debug(f"Filtering cached data with user patterns: {user_facility_patterns}")
            
            # Get all controllers from cached data
            all_controllers = (
                cached_data.get('main_controllers', []) +
                cached_data.get('supporting_above', []) +
                cached_data.get('supporting_below', [])
            )
            
            # Filter controllers by user's patterns
            filtered_main = self._filter_controllers_by_patterns(
                all_controllers, user_facility_patterns.get('main_facility', [])
            )
            filtered_above = self._filter_controllers_by_patterns(
                all_controllers, user_facility_patterns.get('supporting_above', [])
            )
            filtered_below = self._filter_controllers_by_patterns(
                all_controllers, user_facility_patterns.get('supporting_below', [])
            )
            
            # Determine user-specific status
            user_status = self._determine_user_status(filtered_main, filtered_above, filtered_below)
            
            # Create user-specific facility names for display
            user_facility_names = self._get_user_facility_display_names(user_facility_patterns)
            
            # Create filtered response
            filtered_data = cached_data.copy()
            filtered_data.update({
                'status': user_status,
                'facility_name': 'Your Monitored Facilities',
                'main_controllers': filtered_main,
                'supporting_above': filtered_above,
                'supporting_below': filtered_below,
                'using_user_config': True,
                'facility_names': user_facility_names
            })
            
            return filtered_data
            
        except Exception as e:
            logging.error(f"Error filtering cached status for user: {e}")
            return None
    
    def _filter_controllers_by_patterns(self, controllers: List[Dict[str, Any]], patterns: List[str]) -> List[Dict[str, Any]]:
        """
        Filter controllers by regex patterns
        
        Args:
            controllers: List of controller dictionaries
            patterns: List of regex patterns to match against callsigns
        
        Returns:
            List of controllers matching the patterns
        """
        if not patterns:
            return []
        
        import re
        filtered_controllers = []
        
        for controller in controllers:
            callsign = controller.get('callsign', '')
            for pattern in patterns:
                try:
                    if re.match(pattern, callsign):
                        filtered_controllers.append(controller)
                        break  # Don't add the same controller multiple times
                except re.error:
                    # If regex fails, try exact match
                    if pattern == callsign:
                        filtered_controllers.append(controller)
                        break
        
        return filtered_controllers
    
    def _determine_user_status(self, main_controllers: List, supporting_above: List, supporting_below: List) -> str:
        """
        Determine status based on filtered controller lists
        
        Args:
            main_controllers: List of main facility controllers
            supporting_above: List of supporting above controllers
            supporting_below: List of supporting below controllers
        
        Returns:
            Status string
        """
        if main_controllers and supporting_above:
            return 'main_facility_and_supporting_above_online'
        elif main_controllers:
            return 'main_facility_online'
        elif supporting_above:
            return 'supporting_above_online'
        else:
            return 'all_offline'
    
    def _get_user_facility_display_names(self, user_patterns: Dict[str, List[str]]) -> Dict[str, str]:
        """
        Generate display names from user facility patterns
        
        Args:
            user_patterns: User's facility patterns dictionary
        
        Returns:
            Dictionary with display names for each facility type
        """
        import re
        facility_names = {}
        
        for facility_type, patterns in user_patterns.items():
            if not patterns:
                continue
                
            # Use the first pattern to derive a display name
            pattern = patterns[0]
            display_name = None
            
            # Try to extract a clean callsign from the regex pattern
            if re.match(r'^[A-Z0-9_]+$', pattern) and not any(char in pattern for char in ['^', '$', '\\', '(', ')', '?', '+', '*', '[', ']', '{', '}']):
                # It's already a plain callsign
                display_name = pattern
            else:
                # Remove regex anchors and try to extract the core callsign
                clean_pattern = pattern.replace('^', '').replace('$', '')
                
                # Look for common callsign patterns
                simple_match = re.search(r'^([A-Z]{3,4}_[A-Z]{2,4})$', clean_pattern)
                if simple_match:
                    display_name = simple_match.group(1)
                else:
                    # Try more complex extraction
                    callsign_match = re.search(r'([A-Z]{3,4})_([A-Z]{2,4})', clean_pattern)
                    if callsign_match:
                        display_name = f"{callsign_match.group(1)}_{callsign_match.group(2)}"
            
            # If we have multiple patterns, show count
            if len(patterns) > 1:
                if display_name:
                    facility_names[facility_type] = f"{display_name} (+{len(patterns)-1} more)"
                else:
                    facility_names[facility_type] = f"{len(patterns)} facilities"
            else:
                facility_names[facility_type] = display_name or f"{facility_type.replace('_', ' ').title()}"
        
        return facility_names
    
    def monitoring_loop(self):
        """
        Main monitoring loop that runs in background thread
        """
        logging.info("Web monitoring service started")
        
        while self.running:
            try:
                # Check current status with aggregated patterns
                current_result = self.check_status_with_aggregated_config()
                
                if current_result['success']:
                    # Check if status has changed
                    if self.has_status_changed(current_result):
                        logging.info("Status change detected - triggering bulk notifications")
                        
                        # Send bulk notifications to all users based on their individual configurations
                        if self.notification_manager:
                            try:
                                # This will check each user's individual patterns against current VATSIM data
                                # and send personalized notifications only to users whose facilities have changed
                                self.notification_manager.send_bulk_pushover_notification(
                                    title="Facility Status Update",
                                    message="VATSIM facility status has changed",
                                    status=current_result['status']
                                )
                            except Exception as e:
                                logging.error(f"Error sending bulk notifications: {e}")
                        
                        # Update previous status
                        self.update_previous_status(current_result)
                
                    # Always cache the latest result for UI consumption
                    self.update_cached_status(current_result)
                else:
                    logging.warning(f"Status check failed: {current_result.get('error', 'Unknown error')}")
                    # Cache error result too so UI shows appropriate error state
                    self.update_cached_status(current_result)
                
                # Sleep in small chunks to allow quick shutdown
                sleep_time = self.check_interval
                sleep_chunk = 1.0  # 1 second chunks
                
                while sleep_time > 0 and self.running:
                    time.sleep(min(sleep_chunk, sleep_time))
                    sleep_time -= sleep_chunk
                    
            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                # Sleep even on error
                time.sleep(min(30, self.check_interval))  # Sleep shorter on errors
        
        logging.info("Web monitoring service stopped")
    
    def start(self):
        """
        Start the monitoring service
        """
        if self.running:
            logging.warning("Web monitoring service already running")
            return
        
        if not self.db_interface.enabled:
            logging.error("Cannot start web monitoring service - database interface not available")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logging.info("Web monitoring service started successfully")
    
    def stop(self):
        """
        Stop the monitoring service
        """
        if not self.running:
            return
        
        logging.info("Stopping web monitoring service...")
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logging.info("Web monitoring service stopped")
    
    def is_running(self) -> bool:
        """
        Check if monitoring service is running
        
        Returns:
            True if running, False otherwise
        """
        return self.running and self.monitor_thread is not None and self.monitor_thread.is_alive()
    
    def force_check(self):
        """
        Force an immediate status check and potential notification
        """
        if not self.running:
            logging.warning("Cannot force check - monitoring service not running")
            return
        
        logging.info("Forcing immediate status check...")
        try:
            current_result = self.check_status_with_aggregated_config()
            
            if current_result['success'] and self.notification_manager:
                # Always trigger bulk notifications on force check
                self.notification_manager.send_bulk_pushover_notification(
                    title="Manual Status Check",
                    message="Forced status check triggered",
                    status=current_result['status']
                )
                
                self.update_previous_status(current_result)
                # Update cache with force check result
                self.update_cached_status(current_result)
                logging.info("Force check completed successfully")
            else:
                logging.warning(f"Force check failed: {current_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logging.error(f"Error during force check: {e}")


# Global web monitoring service instance
web_monitoring_service = WebMonitoringService()