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
            
            # Merge default patterns with user patterns to ensure comprehensive monitoring
            default_patterns = self.config.get("callsigns", {})
            
            for pattern_type in ['main_facility', 'supporting_above', 'supporting_below']:
                # Start with default patterns
                merged_patterns = list(default_patterns.get(pattern_type, []))
                
                # Add unique user patterns
                user_patterns = aggregated_patterns.get(pattern_type, [])
                for pattern in user_patterns:
                    if pattern not in merged_patterns:
                        merged_patterns.append(pattern)
                
                aggregated_patterns[pattern_type] = merged_patterns
            
            aggregated_config['callsigns'] = aggregated_patterns
            
            total_merged = sum(len(patterns) for patterns in aggregated_patterns.values())
            logging.info(f"Created aggregated config with {total_merged} facility patterns")
            
            return aggregated_config
            
        except Exception as e:
            logging.error(f"Error creating aggregated config: {e}")
            return None
    
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
                    }
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