#!/usr/bin/env python3
"""
VATSIM API Worker module for VATSIM Tower Monitor
Handles background monitoring of VATSIM API for controller status.
This is the PyQt6-based threaded worker that uses the shared monitoring service.
"""

import logging
from typing import Dict, Any
from shared.vatsim_core import VATSIMCore
from shared.pyqt_monitoring_service import PyQtMonitoringService


class VATSIMWorker(PyQtMonitoringService):
    """Desktop PyQt6 worker extending PyQt-compatible base monitoring service"""

    def __init__(self, config, parent=None):
        super().__init__(config, parent)
        
        # Create the VATSIM core client
        self.vatsim_core = VATSIMCore(config)
        
        logging.info("Desktop VATSIM worker initialized")

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

    def request_immediate_check(self):
        """Compatibility method for desktop GUI"""
        self.force_check_requested.emit()