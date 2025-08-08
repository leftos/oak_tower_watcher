#!/usr/bin/env python3
"""
Base Monitoring Service
Common functionality for all monitoring services in the VATSIM Tower Monitor project.
Provides threading, lifecycle management, and monitoring loop patterns.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional

from config.config import load_config
from shared.notification_manager import NotificationManager
from shared.utils import load_artcc_roster


class BaseMonitoringService(ABC):
    """Base class for all monitoring services"""
    
    def __init__(self, config=None):
        """
        Initialize base monitoring service
        
        Args:
            config: Configuration dictionary, loads default if None
        """
        self.config = config or load_config()
        self.controller_names = self._load_roster()
        self.notification_manager = NotificationManager(self.config, self.controller_names)
        
        # Threading control
        self.running = False
        self.monitor_thread = None
        self.check_interval = self.config.get("monitoring", {}).get("check_interval", 60)
        self.force_check_flag = False
        
        # Status tracking for change detection
        self.previous_status = "all_offline"
        self.previous_controllers = {
            'main': [],
            'supporting_above': [],
            'supporting_below': []
        }
        
        logging.debug(f"{self.__class__.__name__} base initialization complete")
    
    def _load_roster(self):
        """Load ARTCC roster for controller names"""
        try:
            roster_url = self.config.get("api", {}).get(
                "roster_url", "https://oakartcc.org/about/roster"
            )
            return load_artcc_roster(roster_url)
        except Exception as e:
            logging.error(f"Error loading roster: {e}")
            return {}
    
    def has_status_changed(self, current_result: Dict[str, Any]) -> bool:
        """
        Check if status has changed (consolidated logic from all monitoring services)
        
        Args:
            current_result: Current status check result
            
        Returns:
            True if status has changed, False otherwise
        """
        if not current_result.get('success'):
            return False
        
        current_status = current_result['status']
        current_main = current_result.get('main_controllers', [])
        current_above = current_result.get('supporting_above', [])
        current_below = current_result.get('supporting_below', [])
        
        # Check status change
        if current_status != self.previous_status:
            logging.info(f"Status changed from {self.previous_status} to {current_status}")
            return True
        
        # Check controller lists (using callsign comparison)
        def get_callsigns(controllers):
            return sorted([c.get('callsign', '') for c in controllers])
        
        current_callsigns = {
            'main': get_callsigns(current_main),
            'supporting_above': get_callsigns(current_above),
            'supporting_below': get_callsigns(current_below)
        }
        
        previous_callsigns = {
            'main': get_callsigns(self.previous_controllers['main']),
            'supporting_above': get_callsigns(self.previous_controllers['supporting_above']),
            'supporting_below': get_callsigns(self.previous_controllers['supporting_below'])
        }
        
        if current_callsigns != previous_callsigns:
            logging.info("Controller lists have changed")
            return True
        
        return False
    
    def update_previous_status(self, current_result: Dict[str, Any]):
        """
        Update stored previous status
        
        Args:
            current_result: Current status check result
        """
        if current_result.get('success'):
            self.previous_status = current_result['status']
            self.previous_controllers = {
                'main': current_result.get('main_controllers', []),
                'supporting_above': current_result.get('supporting_above', []),
                'supporting_below': current_result.get('supporting_below', [])
            }
    
    def sleep_with_force_check(self, sleep_time=None):
        """
        Sleep in chunks while checking for force check and stop signals
        
        Args:
            sleep_time: Time to sleep (uses check_interval if None)
        """
        sleep_time = sleep_time or self.check_interval
        sleep_chunk = 0.5  # Sleep in 0.5 second chunks
        
        while sleep_time > 0 and self.running:
            if self.force_check_flag:
                self.force_check_flag = False
                logging.info("Force check requested, breaking sleep cycle")
                break
            
            chunk_size = min(sleep_chunk, sleep_time)
            time.sleep(chunk_size)
            sleep_time -= chunk_size
    
    def force_check(self):
        """Request immediate status check"""
        self.force_check_flag = True
        logging.info("Force check requested")
    
    def set_interval(self, interval):
        """
        Set check interval
        
        Args:
            interval: Check interval in seconds (minimum 30)
        """
        self.check_interval = max(30, interval)
        logging.info(f"Check interval updated to {self.check_interval} seconds")
    
    @abstractmethod
    def check_status(self) -> Dict[str, Any]:
        """
        Check current status - implemented by subclasses
        
        Returns:
            Status result dictionary with keys: success, status, main_controllers, 
            supporting_above, supporting_below, timestamp, error (if failed)
        """
        pass
    
    @abstractmethod
    def on_status_changed(self, current_result: Dict[str, Any]):
        """
        Handle status changes - implemented by subclasses
        
        Args:
            current_result: Current status check result
        """
        pass
    
    def on_status_updated(self, current_result: Dict[str, Any]):
        """
        Called after every status check - override if needed for caching, etc.
        
        Args:
            current_result: Current status check result
        """
        pass
    
    def on_error(self, error_message: str):
        """
        Handle errors - override if needed
        
        Args:
            error_message: Error message to handle
        """
        logging.error(f"Monitoring error in {self.__class__.__name__}: {error_message}")
    
    def monitoring_loop(self):
        """Base monitoring loop"""
        logging.info(f"{self.__class__.__name__} monitoring started")
        
        while self.running:
            try:
                current_result = self.check_status()
                
                if current_result.get('success'):
                    # Check if status has changed and handle transitions
                    if self.has_status_changed(current_result):
                        logging.info("Status change detected")
                        self.on_status_changed(current_result)
                        self.update_previous_status(current_result)
                    
                    # Always call status updated hook (for caching, etc.)
                    self.on_status_updated(current_result)
                else:
                    error_msg = current_result.get('error', 'Unknown error')
                    self.on_error(error_msg)
                
                # Sleep with responsiveness to force checks and shutdown
                self.sleep_with_force_check()
                
            except Exception as e:
                error_msg = f"Unexpected error in monitoring loop: {e}"
                logging.error(error_msg)
                self.on_error(error_msg)
                
                # Sleep shorter on errors
                error_sleep_time = min(30, self.check_interval)
                self.sleep_with_force_check(error_sleep_time)
        
        logging.info(f"{self.__class__.__name__} monitoring stopped")
    
    def start(self):
        """Start monitoring service"""
        if self.running:
            logging.warning(f"{self.__class__.__name__} already running")
            return
        
        self.running = True
        
        # Perform initial status check before starting the monitoring loop
        self._perform_initial_check()
        
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logging.info(f"{self.__class__.__name__} started successfully")
    
    def _perform_initial_check(self):
        """
        Perform an initial status check on startup
        This ensures fresh data is available immediately after service start
        """
        logging.info(f"Performing initial status check for {self.__class__.__name__}...")
        
        try:
            current_result = self.check_status()
            
            if current_result.get('success'):
                logging.info(f"Initial status check successful for {self.__class__.__name__}")
                
                # Check if status has changed and handle transitions
                if self.has_status_changed(current_result):
                    logging.info("Status change detected during initial check")
                    self.on_status_changed(current_result)
                    self.update_previous_status(current_result)
                
                # Always call status updated hook (for caching, etc.)
                self.on_status_updated(current_result)
            else:
                error_msg = current_result.get('error', 'Unknown error during initial check')
                logging.warning(f"Initial status check failed for {self.__class__.__name__}: {error_msg}")
                self.on_error(error_msg)
                
        except Exception as e:
            error_msg = f"Error during initial status check for {self.__class__.__name__}: {e}"
            logging.error(error_msg, exc_info=True)
            self.on_error(error_msg)
    
    def stop(self):
        """Stop monitoring service"""
        if not self.running:
            return
        
        logging.info(f"Stopping {self.__class__.__name__}...")
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
            if self.monitor_thread.is_alive():
                logging.warning(f"{self.__class__.__name__} thread did not stop within timeout")
        
        logging.info(f"{self.__class__.__name__} stopped")
    
    def is_running(self) -> bool:
        """
        Check if service is running
        
        Returns:
            True if running, False otherwise
        """
        return self.running and self.monitor_thread is not None and self.monitor_thread.is_alive()
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get current service status summary
        
        Returns:
            Dictionary with service status information
        """
        return {
            'running': self.is_running(),
            'check_interval': self.check_interval,
            'previous_status': self.previous_status,
            'controller_count': {
                'main': len(self.previous_controllers.get('main', [])),
                'supporting_above': len(self.previous_controllers.get('supporting_above', [])),
                'supporting_below': len(self.previous_controllers.get('supporting_below', []))
            },
            'service_name': self.__class__.__name__
        }