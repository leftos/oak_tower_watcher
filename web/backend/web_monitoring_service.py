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
from shared.base_monitoring_service import BaseMonitoringService
from shared.database_interface import DatabaseInterface
from shared.utils import load_artcc_roster


class WebMonitoringService(BaseMonitoringService):
    """
    Web-specific monitoring service that monitors all facilities users care about
    """
    
    def __init__(self):
        super().__init__()
        
        # Web-specific components
        self.db_interface = DatabaseInterface()
        
        # Cached status data for UI consumption
        self._cached_status = None
        self._cache_lock = threading.Lock()
        self.last_cache_update = None
        
        logging.info("Web monitoring service initialized")
    
    def check_status(self) -> Dict[str, Any]:
        """Check status using comprehensive data collection (implements abstract method)"""
        return self.check_status_comprehensive()

    def on_status_changed(self, current_result: Dict[str, Any]):
        """Handle status changes with bulk notifications (implements abstract method)"""
        if current_result.get('success') and self.notification_manager:
            try:
                # For comprehensive monitoring, send notifications based on significant network changes
                total_controllers = current_result.get('total_controllers', 0)
                
                # Send bulk notifications to all users based on their individual configurations
                # The notification manager will handle filtering for each user's specific patterns
                self.notification_manager.send_bulk_pushover_notification(
                    title="VATSIM Network Update",
                    message=f"VATSIM network status update - {total_controllers} controllers online",
                    status="network_update"
                )
                logging.info(f"Sent bulk notifications for network change - {total_controllers} controllers")
            except Exception as e:
                logging.error(f"Error sending bulk notifications: {e}")

    def on_status_updated(self, current_result: Dict[str, Any]):
        """Update cache on every status check (overrides base method)"""
        self.update_cached_status(current_result)

    def has_status_changed(self, current_result: Dict[str, Any]) -> bool:
        """
        Always trigger notifications for user-centric monitoring
        The notification system will handle checking individual user changes
        
        Args:
            current_result: Current comprehensive status check result
            
        Returns:
            True if VATSIM data was successfully retrieved, False otherwise
        """
        return current_result.get('success', False)

    def update_previous_status(self, current_result: Dict[str, Any]):
        """
        Update stored previous status for comprehensive data
        Override base method since comprehensive data has different structure
        
        Args:
            current_result: Current comprehensive status check result
        """
        if current_result.get('success'):
            # For user-centric monitoring, we set a generic status for base class compatibility
            total_controllers = current_result.get('total_controllers', 0)
            self.previous_status = f"user_centric_monitoring_{total_controllers}_controllers"
            # Clear controller lists since we don't use them in comprehensive mode
            self.previous_controllers = {
                'main': [],
                'supporting_above': [],
                'supporting_below': []
            }
    
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
    
    def _clean_regex_pattern_to_callsign(self, pattern: str, facility_type: Optional[str] = None) -> str:
        r"""
        Extract a clean, user-friendly callsign from a regex pattern
        
        Args:
            pattern: The regex pattern to clean (e.g., "^OAK_(?:[A-Z\d]+_)?TWR$")
            facility_type: Optional facility type for fallback naming
            
        Returns:
            Cleaned callsign string (e.g., "OAK_TWR")
        """
        import re
        
        try:
            # Check if it's already a simple callsign (no regex special characters)
            if re.match(r'^[A-Z0-9_]+$', pattern) and not any(char in pattern for char in ['^', '$', '\\', '(', ')', '?', '+', '*', '[', ']', '{', '}']):
                logging.debug(f"Pattern is already a plain callsign: {pattern}")
                return pattern
            
            # Remove regex anchors
            clean_pattern = pattern.replace('^', '').replace('$', '')
            
            # Handle simple patterns first (like SAN_TWR, SCT_APP, SAN_GND)
            simple_match = re.search(r'^([A-Z]{3,4}_[A-Z]{2,4})$', clean_pattern)
            if simple_match:
                result = simple_match.group(1)
                logging.debug(f"Extracted simple callsign: {result} from pattern: {pattern}")
                return result
            
            # Handle complex patterns - look for core facility identifiers first
            # This handles patterns like "OAK_(?:[A-Z\d]+_)?TWR" -> "OAK_TWR"
            core_match = re.search(r'([A-Z]{3,4})_.*?([A-Z]{2,4})$', clean_pattern)
            if core_match:
                result = f"{core_match.group(1)}_{core_match.group(2)}"
                logging.debug(f"Extracted core callsign: {result} from pattern: {pattern}")
                return result
            
            # Apply generic cleaning for more complex cases
            clean_pattern = clean_pattern.replace('\\d+', '').replace('\\', '').replace('(?:', '').replace(')?', '').replace('_+', '_')
            clean_pattern = re.sub(r'_+', '_', clean_pattern).strip('_')
            
            # Look for common callsign patterns
            callsign_match = re.search(r'([A-Z]{3,4})_([A-Z]{2,4})', clean_pattern)
            if callsign_match:
                result = f"{callsign_match.group(1)}_{callsign_match.group(2)}"
                logging.debug(f"Extracted callsign after cleaning: {result} from pattern: {pattern}")
                return result
            
            # Try to find any combination of letters and underscores as fallback
            letters_match = re.search(r'([A-Z_]+)', clean_pattern)
            if letters_match:
                name = letters_match.group(1).strip('_')
                # If it doesn't have an underscore, try to complete it based on facility type
                if '_' not in name and facility_type:
                    suffix_map = {
                        'main_facility': '_TWR',
                        'supporting_above': '_APP',
                        'supporting_below': '_GND'
                    }
                    name += suffix_map.get(facility_type, '')
                
                logging.debug(f"Extracted fallback callsign: {name} from pattern: {pattern}")
                return name
            
            # Final fallback - return a generic name based on facility type
            if facility_type:
                fallback = f"{facility_type.replace('_', ' ').title()}"
                logging.debug(f"Using fallback name: {fallback} for pattern: {pattern}")
                return fallback
            
            logging.warning(f"Could not extract callsign from pattern: {pattern}")
            return "Unknown Facility"
            
        except Exception as e:
            logging.error(f"Error cleaning regex pattern '{pattern}': {e}")
            return facility_type.replace('_', ' ').title() if facility_type else "Unknown Facility"
    
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
                    # Use the first pattern to derive a display name
                    cleaned_name = self._clean_regex_pattern_to_callsign(patterns[0], facility_type)
                    facility_names[facility_type] = cleaned_name
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
    
    def check_status_comprehensive(self) -> Dict[str, Any]:
        """
        Check VATSIM status using comprehensive data collection
        Collects ALL active controllers, not just user-configured patterns
        
        Returns:
            Comprehensive status result dictionary with all controllers
        """
        try:
            # Create VATSIMCore with default config (patterns don't matter for comprehensive collection)
            vatsim_core = VATSIMCore(self.config)
            
            # Get comprehensive controller data
            result = vatsim_core.check_status_comprehensive()
            
            if result['success']:
                logging.debug(f"Comprehensive status check successful: {result['total_controllers']} controllers collected")
            else:
                logging.warning(f"Comprehensive status check failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logging.error(f"Error checking comprehensive status: {e}")
            return {
                'success': False,
                'error': str(e),
                'all_controllers': [],
                'timestamp': datetime.now().isoformat(),
                'total_controllers': 0
            }

    def check_status_with_aggregated_config(self) -> Dict[str, Any]:
        """
        Check VATSIM status using aggregated facility patterns from all users
        DEPRECATED: Use check_status_comprehensive() for new architecture
        
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
    
    
    def update_cached_status(self, status_result: Dict[str, Any]):
        """
        Update cached status data for UI consumption
        Now stores comprehensive controller data instead of filtered data
        
        Args:
            status_result: Latest comprehensive status check result
        """
        try:
            with self._cache_lock:
                self._cached_status = {
                    # Store comprehensive controller data
                    'all_controllers': status_result.get('all_controllers', []),
                    'timestamp': status_result.get('timestamp', datetime.now().isoformat()),
                    'success': status_result.get('success', False),
                    'error': status_result.get('error'),
                    'total_controllers': status_result.get('total_controllers', 0),
                    'config': {
                        'check_interval': self.check_interval
                    },
                    'monitoring_service': {
                        'using_comprehensive_cache': True,
                        'running': self.is_running()
                    }
                }
                self.last_cache_update = datetime.now()
                
                total_controllers = status_result.get('total_controllers', 0)
                logging.debug(f"Updated comprehensive cached status: {total_controllers} controllers")
                
        except Exception as e:
            logging.error(f"Error updating cached status: {e}")
    
    def get_cached_status(self) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive cached controller data
        
        Returns:
            Cached comprehensive controller data or None if no data available
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
        Get user-specific status by filtering comprehensive cached data in real-time
        
        Args:
            user_facility_patterns: Dictionary with keys 'main_facility', 'supporting_above', 'supporting_below'
                                  and values as lists of regex patterns
        
        Returns:
            Filtered status dictionary or None if no cached data available
        """
        try:
            # Get comprehensive cached controller data
            cached_data = self.get_cached_status()
            if cached_data is None:
                return None
            
            # Get all active controllers from cache
            all_controllers = cached_data.get('all_controllers', [])
            
            # If no user patterns provided, use default config patterns to filter the data
            if not user_facility_patterns or not any(user_facility_patterns.values()):
                # Use default config patterns instead of returning empty lists
                default_config_patterns = self.config.get('callsigns', {})
                default_facility_names = self._get_user_facility_display_names(default_config_patterns)
                
                logging.debug(f"No user patterns provided, using default config patterns: {default_config_patterns}")
                
                # Filter using default patterns
                vatsim_core = VATSIMCore(self.config)
                filtered_main, filtered_above, filtered_below = vatsim_core.filter_comprehensive_data(
                    all_controllers, default_config_patterns
                )
                
                # Determine status based on filtered results
                default_status = self._determine_user_status(filtered_main, filtered_above, filtered_below)
                
                # Return filtered data using default config patterns
                return {
                    'status': default_status,
                    'facility_name': 'Monitored Facilities',
                    'main_controllers': filtered_main,
                    'supporting_above': filtered_above,
                    'supporting_below': filtered_below,
                    'using_user_config': False,
                    'facility_names': default_facility_names or {
                        'main_facility': 'Main Facility',
                        'supporting_above': 'Supporting Above',
                        'supporting_below': 'Supporting Below'
                    },
                    'filtered_counts': {
                        'main': len(filtered_main),
                        'supporting_above': len(filtered_above),
                        'supporting_below': len(filtered_below)
                    },
                    'timestamp': cached_data.get('timestamp'),
                    'cache_age_seconds': cached_data.get('cache_age_seconds'),
                    'last_updated': cached_data.get('last_updated'),
                    'success': cached_data.get('success'),
                    'total_controllers': cached_data.get('total_controllers', 0),
                    'config': cached_data.get('config', {}),
                    'monitoring_service': cached_data.get('monitoring_service', {})
                }
            
            logging.debug(f"Filtering {len(all_controllers)} controllers with user patterns: {user_facility_patterns}")
            
            # Create VATSIMCore instance for filtering (config doesn't matter for filtering)
            vatsim_core = VATSIMCore(self.config)
            
            # Filter controllers using VATSIMCore filtering methods
            filtered_main, filtered_above, filtered_below = vatsim_core.filter_comprehensive_data(
                all_controllers, user_facility_patterns
            )
            
            # Determine user-specific status
            user_status = self._determine_user_status(filtered_main, filtered_above, filtered_below)
            
            # Create user-specific facility names for display
            user_facility_names = self._get_user_facility_display_names(user_facility_patterns)
            
            # Create filtered response with comprehensive cache metadata
            filtered_data = {
                'status': user_status,
                'facility_name': 'Your Monitored Facilities',
                'main_controllers': filtered_main,
                'supporting_above': filtered_above,
                'supporting_below': filtered_below,
                'using_user_config': True,
                'facility_names': user_facility_names,
                'timestamp': cached_data.get('timestamp'),
                'cache_age_seconds': cached_data.get('cache_age_seconds'),
                'last_updated': cached_data.get('last_updated'),
                'success': cached_data.get('success'),
                'total_controllers': cached_data.get('total_controllers', 0),
                'filtered_counts': {
                    'main': len(filtered_main),
                    'supporting_above': len(filtered_above),
                    'supporting_below': len(filtered_below)
                },
                'config': cached_data.get('config', {}),
                'monitoring_service': cached_data.get('monitoring_service', {})
            }
            
            logging.debug(f"User filtered status: {user_status} ({len(filtered_main)}/{len(filtered_above)}/{len(filtered_below)} controllers)")
            return filtered_data
            
        except Exception as e:
            logging.error(f"Error filtering cached status for user: {e}")
            return None
    
    
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
                # Remove regex anchors and escape characters, but preserve the core callsign
                clean_pattern = pattern.replace('^', '').replace('$', '')
                
                # Handle simple patterns first (like ^SAN_TWR$, ^SCT_APP$, ^SAN_GND$)
                simple_match = re.search(r'^([A-Z]{3,4}_[A-Z]{2,4})$', clean_pattern)
                if simple_match:
                    display_name = simple_match.group(1)
                else:
                    # Handle more complex patterns - look for core facility identifiers first
                    # Try to extract the base pattern by looking for fixed parts
                    core_match = re.search(r'([A-Z]{3,4})_.*?([A-Z]{2,4})$', clean_pattern)
                    if core_match:
                        display_name = f"{core_match.group(1)}_{core_match.group(2)}"
                    else:
                        # Apply more generic cleaning logic as fallback
                        clean_pattern = clean_pattern.replace('\\d+', '').replace('\\', '').replace('(?:', '').replace(')?', '').replace('_+', '_')
                        # Clean up consecutive underscores and trim
                        clean_pattern = re.sub(r'_+', '_', clean_pattern).strip('_')
                        
                        # Look for common callsign patterns like XXX_TWR, XXX_APP, XXX_GND, etc.
                        callsign_match = re.search(r'([A-Z]{3,4})_([A-Z]{2,4})', clean_pattern)
                        if callsign_match:
                            display_name = f"{callsign_match.group(1)}_{callsign_match.group(2)}"
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
                                display_name = name
            
            # If we have multiple patterns, show count
            if len(patterns) > 1:
                if display_name:
                    facility_names[facility_type] = f"{display_name} (+{len(patterns)-1} more)"
                else:
                    facility_names[facility_type] = f"{len(patterns)} facilities"
            else:
                facility_names[facility_type] = display_name or f"{facility_type.replace('_', ' ').title()}"
        
        return facility_names
    
    def start(self):
        """Start the web monitoring service"""
        # Note: Database interface is still needed for notifications, but not for monitoring status collection
        if not self.db_interface.enabled:
            logging.warning("Database interface not available - bulk notifications will be disabled")
        
        super().start()
        logging.info("Web monitoring service started successfully (comprehensive data collection mode)")
    
    def force_check(self):
        """Force an immediate comprehensive status check"""
        if not self.is_running():
            logging.warning("Cannot force check - monitoring service not running")
            return
        
        logging.info("Forcing immediate comprehensive status check...")
        try:
            # Use base class force check mechanism
            super().force_check()
            
            # Additional web-specific force check handling
            current_result = self.check_status_comprehensive()
            
            if current_result.get('success') and self.notification_manager:
                # Trigger bulk notifications on force check
                # Note: Notifications still use individual user patterns, but monitoring collects comprehensive data
                self.notification_manager.send_bulk_pushover_notification(
                    title="Manual Status Check",
                    message="Forced comprehensive status check triggered",
                    status="manual_check"
                )
                logging.info(f"Force check completed successfully - collected {current_result.get('total_controllers', 0)} controllers")
            else:
                logging.warning(f"Force check failed: {current_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logging.error(f"Error during force check: {e}")


# Global web monitoring service instance
web_monitoring_service = WebMonitoringService()