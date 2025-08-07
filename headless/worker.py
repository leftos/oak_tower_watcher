#!/usr/bin/env python3
"""
Headless VATSIM API Worker module for VATSIM Tower Monitor
Handles background monitoring of VATSIM API for controller status without PyQt6 dependencies.
"""

import logging
import sys
import os
from typing import Callable, Optional, Dict, Any

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.vatsim_core import VATSIMCore
from shared.base_monitoring_service import BaseMonitoringService


class HeadlessVATSIMWorker(BaseMonitoringService):
    """Headless worker extending base monitoring service for backward compatibility"""

    def __init__(self, config):
        super().__init__(config)
        
        # Create the VATSIM core client
        self.vatsim_core = VATSIMCore(config)
        
        # Callback functions for backward compatibility with existing main.py
        self.status_updated_callback: Optional[Callable] = None
        self.error_occurred_callback: Optional[Callable] = None
        
        # Legacy attributes for compatibility
        self.is_force_check = False
        self.thread = None  # Will be set to monitor_thread by base class

    def check_status(self) -> Dict[str, Any]:
        """Check current status using VATSIM core client"""
        try:
            result = self.vatsim_core.check_status()
            return result
        except Exception as e:
            logging.error(f"Error checking status: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error',
                'main_controllers': [],
                'supporting_above': [],
                'supporting_below': [],
                'timestamp': ""
            }

    def on_status_changed(self, current_result: Dict[str, Any]):
        """Handle status changes via callback for backward compatibility"""
        if self.status_updated_callback:
            try:
                # Extract data for callback format expected by main.py
                status = current_result.get('status', 'error')
                main_controllers = current_result.get('main_controllers', [])
                supporting_above = current_result.get('supporting_above', [])
                supporting_below = current_result.get('supporting_below', [])
                
                # Call the legacy callback
                self.status_updated_callback(
                    status, main_controllers, supporting_above, supporting_below
                )
            except Exception as e:
                logging.error(f"Error in status update callback: {e}")
                if self.error_occurred_callback:
                    self.error_occurred_callback(f"Callback error: {str(e)}")

    def on_error(self, error_message: str):
        """Handle errors via callback for backward compatibility"""
        super().on_error(error_message)
        if self.error_occurred_callback:
            self.error_occurred_callback(error_message)

    def request_immediate_check(self):
        """Request an immediate check (legacy method for compatibility)"""
        self.force_check()
        self.is_force_check = True

    def start(self):
        """Start the worker (delegates to base class)"""
        super().start()
        # Set thread reference for backward compatibility
        self.thread = self.monitor_thread
        logging.info("Headless VATSIM worker started")

    def stop(self):
        """Stop the worker (delegates to base class)"""
        super().stop()
        logging.info("Headless VATSIM worker stopped")