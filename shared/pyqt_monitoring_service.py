#!/usr/bin/env python3
"""
PyQt-Compatible Base Monitoring Service
Provides shared monitoring functionality for PyQt6-based desktop applications.
"""

import logging
from typing import Dict, Any, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from config.config import load_config
from shared.notification_manager import NotificationManager
from shared.utils import load_artcc_roster


class PyQtMonitoringService(QThread):
    """
    PyQt6-compatible monitoring service that provides shared functionality
    
    This class provides the same patterns as BaseMonitoringService but in a
    PyQt6-compatible way using composition instead of multiple inheritance.
    """
    
    # PyQt signals for communication with GUI
    status_updated = pyqtSignal(str, list, list, list)  # status, main, above, below
    force_check_completed = pyqtSignal(str, list, list, list)
    error_occurred = pyqtSignal(str)
    force_check_requested = pyqtSignal()
    
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        
        # Configuration and shared components
        self.config = config or load_config()
        self.controller_names = self._load_roster()
        self.notification_manager = NotificationManager(self.config, self.controller_names)
        
        # Threading control
        self.running = False
        self.check_interval = self.config.get("monitoring", {}).get("check_interval", 60)
        self.force_check_flag = False
        
        # Status tracking for change detection
        self.previous_status = "all_offline"
        self.previous_controllers = {
            'main': [],
            'supporting_above': [],
            'supporting_below': []
        }
        
        # PyQt-specific attributes
        self.is_force_check = False
        
        # Connect force check signal
        self.force_check_requested.connect(self._handle_force_check_request)
        
        logging.debug(f"{self.__class__.__name__} PyQt monitoring service initialized")
    
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
    
    def _handle_force_check_request(self):
        """Handle force check requests from PyQt signals"""
        self.is_force_check = True
        self.force_check_flag = True
    
    def force_check(self):
        """Request immediate status check"""
        self.force_check_flag = True
        logging.info("Force check requested")
    
    def has_status_changed(self, current_result: Dict[str, Any]) -> bool:
        """Check if status has changed (from BaseMonitoringService)"""
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
        """Update stored previous status"""
        if current_result.get('success'):
            self.previous_status = current_result['status']
            self.previous_controllers = {
                'main': current_result.get('main_controllers', []),
                'supporting_above': current_result.get('supporting_above', []),
                'supporting_below': current_result.get('supporting_below', [])
            }
    
    def sleep_with_force_check(self, sleep_time=None):
        """
        PyQt-compatible sleep with force check responsiveness
        Uses QThread.msleep instead of time.sleep for proper Qt integration
        
        Args:
            sleep_time: Time to sleep in seconds (converted to ms for Qt)
        """
        sleep_time_ms = int((sleep_time or self.check_interval) * 1000)
        sleep_chunk_ms = 500  # 500ms chunks
        
        while sleep_time_ms > 0 and self.running:
            if self.force_check_flag:
                self.force_check_flag = False
                logging.info("Force check requested, breaking sleep cycle")
                break
            
            chunk_size = min(sleep_chunk_ms, sleep_time_ms)
            self.msleep(chunk_size)
            sleep_time_ms -= chunk_size
    
    def check_status(self) -> Dict[str, Any]:
        """
        Check current status - must be implemented by subclasses
        
        Returns:
            Status result dictionary with keys: success, status, main_controllers,
            supporting_above, supporting_below, timestamp, error (if failed)
        """
        raise NotImplementedError("Subclasses must implement check_status method")
    
    def on_status_changed(self, current_result: Dict[str, Any]):
        """
        Handle status changes - emit PyQt signals
        
        Args:
            current_result: Current status check result
        """
        if self.is_force_check:
            # Emit force check completed signal
            self.force_check_completed.emit(
                current_result.get('status', 'error'),
                current_result.get('main_controllers', []),
                current_result.get('supporting_above', []),
                current_result.get('supporting_below', [])
            )
            self.is_force_check = False
        else:
            # Emit regular status update signal
            self.status_updated.emit(
                current_result.get('status', 'error'),
                current_result.get('main_controllers', []),
                current_result.get('supporting_above', []),
                current_result.get('supporting_below', [])
            )
    
    def on_error(self, error_message: str):
        """
        Handle errors - emit PyQt signals
        
        Args:
            error_message: Error message to handle
        """
        logging.error(f"Monitoring error in {self.__class__.__name__}: {error_message}")
        self.error_occurred.emit(error_message)
    
    def monitoring_loop(self):
        """PyQt-compatible monitoring loop"""
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
                    
                    # Always call status updated hook
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
    
    def on_status_updated(self, current_result: Dict[str, Any]):
        """
        Called after every status check - override if needed
        
        Args:
            current_result: Current status check result
        """
        pass
    
    def run(self):
        """
        QThread run method - delegates to monitoring loop
        This is called when QThread.start() is invoked
        """
        self.monitoring_loop()
    
    def start_monitoring(self):
        """
        Start the PyQt monitoring thread
        Uses QThread.start() instead of creating new thread
        """
        if self.running:
            logging.warning(f"{self.__class__.__name__} already running")
            return
        
        self.running = True
        # Start QThread (calls run() method)
        QThread.start(self)
        logging.info(f"{self.__class__.__name__} started successfully")
    
    def stop(self):
        """
        Stop the PyQt monitoring thread
        """
        if not self.running:
            return
        
        logging.info(f"Stopping {self.__class__.__name__}...")
        self.running = False
        
        # Use QThread methods for proper cleanup
        self.quit()
        if not self.wait(5000):  # 5 second timeout
            logging.warning(f"{self.__class__.__name__} thread did not stop within timeout")
        
        logging.info(f"{self.__class__.__name__} stopped")
    
    def set_interval(self, interval):
        """
        Set check interval
        
        Args:
            interval: Check interval in seconds (minimum 30)
        """
        self.check_interval = max(30, interval)
        logging.info(f"Check interval updated to {self.check_interval} seconds")