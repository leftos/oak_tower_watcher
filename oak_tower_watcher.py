#!/usr/bin/env python3
"""
VATSIM KOAK Tower Monitor
A system tray application that monitors VATSIM for KOAK tower controllers.
Uses Qt for cross-platform GUI components.
"""

import requests
import json
import threading
from datetime import datetime
import sys
import signal
import logging
import os
import atexit

# fcntl is only available on Unix-like systems
if sys.platform != "win32":
    import fcntl
from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QTextEdit,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QBrush, QPen

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("vatsim_monitor.log"), logging.StreamHandler()],
)

# Global variable to store lock file handle
_lock_file = None


def acquire_instance_lock():
    """
    Acquire an exclusive lock to prevent multiple instances.
    Returns True if lock acquired successfully, False if another instance is running.
    """
    global _lock_file
    lock_file_path = os.path.join(os.path.expanduser("~"), ".vatsim_monitor.lock")

    try:
        _lock_file = open(lock_file_path, "w")

        # Try to acquire exclusive lock
        if sys.platform == "win32":
            # Windows implementation using msvcrt
            import msvcrt

            try:
                msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                # Write PID to lock file
                _lock_file.write(str(os.getpid()))
                _lock_file.flush()
                return True
            except IOError:
                _lock_file.close()
                return False
        else:
            # Unix/Linux implementation using fcntl
            try:
                fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID to lock file
                _lock_file.write(str(os.getpid()))
                _lock_file.flush()
                return True
            except IOError:
                _lock_file.close()
                return False

    except Exception as e:
        logging.error(f"Error acquiring instance lock: {e}")
        if _lock_file:
            _lock_file.close()
        return False


def release_instance_lock():
    """Release the instance lock."""
    global _lock_file
    if _lock_file:
        try:
            if sys.platform != "win32":
                fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()

            # Remove lock file
            lock_file_path = os.path.join(
                os.path.expanduser("~"), ".vatsim_monitor.lock"
            )
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)
        except Exception as e:
            logging.error(f"Error releasing instance lock: {e}")
        finally:
            _lock_file = None


class VATSIMWorker(QThread):
    """Worker thread for VATSIM API calls"""

    status_updated = pyqtSignal(bool, dict)  # tower_online, controller_info
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.check_interval = 60

        # VATSIM API endpoints
        self.vatsim_api_url = "https://data.vatsim.net/v3/vatsim-data.json"

        # KOAK tower callsigns to monitor
        self.koak_tower_callsigns = [
            "OAK_TWR",
            "OAK_1_TWR",
        ]

    def set_interval(self, interval):
        """Set check interval"""
        self.check_interval = max(30, interval)  # Minimum 30 seconds

    def query_vatsim_api(self):
        """Query VATSIM API for controller data"""
        try:
            logging.info("Querying VATSIM API...")
            response = requests.get(self.vatsim_api_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            controllers = data.get("controllers", [])

            # Look for KOAK tower controllers
            koak_controllers = []
            for controller in controllers:
                callsign = controller.get("callsign", "")
                if any(
                    tower_call in callsign.upper()
                    for tower_call in self.koak_tower_callsigns
                ):
                    koak_controllers.append(controller)

            return koak_controllers

        except requests.exceptions.RequestException as e:
            logging.error(f"Error querying VATSIM API: {e}")
            self.error_occurred.emit(f"API Error: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing VATSIM API response: {e}")
            self.error_occurred.emit(f"JSON Error: {str(e)}")
            return None

    def check_tower_status(self):
        """Check if KOAK tower is online"""
        controllers = self.query_vatsim_api()

        if controllers is None:
            # API error - don't change status
            return

        if controllers:
            controller_info = controllers[0]  # Use first controller found
            logging.info(
                f"KOAK Tower ONLINE: {controller_info['callsign']} - {controller_info.get('name', 'Unknown')}"
            )
            self.status_updated.emit(True, controller_info)
        else:
            logging.info("KOAK Tower OFFLINE")
            self.status_updated.emit(False, {})

    def run(self):
        """Main monitoring loop"""
        self.running = True
        while self.running:
            try:
                self.check_tower_status()

                # Sleep in small intervals to allow quick response to stop signals
                sleep_time = self.check_interval * 1000  # Convert to milliseconds
                sleep_chunk = 500  # Sleep in 500ms chunks

                while sleep_time > 0 and self.running:
                    chunk_size = min(sleep_chunk, sleep_time)
                    self.msleep(chunk_size)
                    sleep_time -= chunk_size

            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                self.error_occurred.emit(f"Monitoring Error: {str(e)}")

                # Also sleep in chunks during error recovery
                sleep_time = self.check_interval * 1000
                sleep_chunk = 500

                while sleep_time > 0 and self.running:
                    chunk_size = min(sleep_chunk, sleep_time)
                    self.msleep(chunk_size)
                    sleep_time -= chunk_size

    def stop(self):
        """Stop the worker thread"""
        self.running = False
        self.quit()
        # Wait for thread to finish - should be quick now with chunked sleep
        self.wait(2000)  # 2 second timeout should be plenty


class StatusDialog(QDialog):
    """Dialog to show current tower status"""

    def __init__(self, tower_online, controller_info, last_check, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KOAK Tower Status")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout()

        # Status header
        status = "ONLINE" if tower_online else "OFFLINE"
        color = "🟢" if tower_online else "🔴"

        status_label = QLabel(f"{color} KOAK Tower: {status}")
        status_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")

        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)

        # Controller details
        details_text = QTextEdit()
        details_text.setReadOnly(True)

        if tower_online and controller_info:
            details = f"""Controller Information:

Callsign: {controller_info.get('callsign', 'Unknown')}
Name: {controller_info.get('name', 'Unknown')}
Frequency: {controller_info.get('frequency', 'Unknown')}
Rating: {controller_info.get('rating', 'Unknown')}
Logon Time: {controller_info.get('logon_time', 'Unknown')}
Server: {controller_info.get('server', 'Unknown')}"""
        else:
            details = "No KOAK tower controller currently online."

        if last_check:
            details += f"\n\nLast checked: {last_check.strftime('%Y-%m-%d %H:%M:%S')}"

        details_text.setPlainText(details)
        layout.addWidget(details_text)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)


class SettingsDialog(QDialog):
    """Dialog for application settings"""

    def __init__(self, current_interval, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VATSIM Monitor Settings")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        # Interval setting
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Check Interval (seconds):"))

        self.interval_input = QLineEdit(str(current_interval))
        interval_layout.addWidget(self.interval_input)
        layout.addLayout(interval_layout)

        # Buttons
        button_layout = QHBoxLayout()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.new_interval = current_interval

    def save_settings(self):
        """Save settings and close dialog"""
        try:
            interval = int(self.interval_input.text())
            if interval >= 30:
                self.new_interval = interval
                self.accept()
            else:
                QMessageBox.warning(
                    self, "Invalid Input", "Check interval must be at least 30 seconds."
                )
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")


class VATSIMMonitor(QApplication):
    """Main application class"""

    def __init__(self, argv):
        super().__init__(argv)

        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(
                None, "System Tray", "System tray is not available on this system."
            )
            sys.exit(1)

        # Application state
        self.tower_online = False
        self.controller_info = {}
        self.last_check = None
        self.monitoring = False
        self._shutting_down = False

        # Setup components
        self.setup_tray_icon()
        self.setup_worker()

        # Don't quit when last window closes (for tray apps)
        self.setQuitOnLastWindowClosed(False)

        # Setup signal processing timer for immediate Ctrl+C handling
        self.setup_signal_timer()

    def create_icon(self, color="gray"):
        """Create a colored circle icon"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if color == "green":
            brush = QBrush(Qt.GlobalColor.green)
        elif color == "red":
            brush = QBrush(Qt.GlobalColor.red)
        else:  # gray
            brush = QBrush(Qt.GlobalColor.gray)

        painter.setBrush(brush)
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()

        return QIcon(pixmap)

    def setup_tray_icon(self):
        """Setup system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_icon("gray"))
        self.tray_icon.setToolTip("VATSIM KOAK Monitor")

        # Create menu
        tray_menu = QMenu()

        # Status action
        status_action = QAction("KOAK Tower Status", self)
        status_action.triggered.connect(self.show_status)
        tray_menu.addAction(status_action)

        # Check now action
        check_action = QAction("Check Now", self)
        check_action.triggered.connect(self.force_check)
        tray_menu.addAction(check_action)

        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        # Start/Stop monitoring
        self.start_action = QAction("Start Monitoring", self)
        self.start_action.triggered.connect(self.start_monitoring)
        tray_menu.addAction(self.start_action)

        self.stop_action = QAction("Stop Monitoring", self)
        self.stop_action.triggered.connect(self.stop_monitoring)
        self.stop_action.setEnabled(False)
        tray_menu.addAction(self.stop_action)

        tray_menu.addSeparator()

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Connect double-click to show status
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def setup_signal_timer(self):
        """Setup timer to process signals immediately"""
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(lambda: None)  # Just process events
        self.signal_timer.start(100)  # Check every 100ms for signals

    def setup_worker(self):
        """Setup the VATSIM worker thread"""
        self.worker = VATSIMWorker()
        self.worker.status_updated.connect(self.on_status_updated)
        self.worker.error_occurred.connect(self.on_error)

    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_status()

    def on_status_updated(self, tower_online, controller_info):
        """Handle status update from worker thread"""
        previous_status = self.tower_online
        self.tower_online = tower_online
        self.controller_info = controller_info
        self.last_check = datetime.now()

        # Update tray icon
        color = "green" if tower_online else "red"
        self.tray_icon.setIcon(self.create_icon(color))

        # Show notification if status changed
        if tower_online != previous_status:
            if tower_online:
                message = f"{controller_info.get('callsign', 'Unknown')} is now online!"
                if controller_info.get("name"):
                    message += f"\nController: {controller_info['name']}"
                self.tray_icon.showMessage(
                    "KOAK Tower Online!",
                    message,
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
            else:
                self.tray_icon.showMessage(
                    "KOAK Tower Offline",
                    "No tower controller found",
                    QSystemTrayIcon.MessageIcon.Warning,
                    3000,
                )

    def on_error(self, error_message):
        """Handle error from worker thread"""
        logging.error(error_message)
        self.tray_icon.setIcon(self.create_icon("gray"))

    def start_monitoring(self):
        """Start monitoring VATSIM"""
        if not self.monitoring:
            self.monitoring = True
            self.worker.start()

            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)

            # self.tray_icon.showMessage(
            #     "VATSIM Monitor Started",
            #     "Monitoring KOAK tower status",
            #     QSystemTrayIcon.MessageIcon.Information,
            #     2000,
            # )
            logging.info("Started VATSIM monitoring")

    def stop_monitoring(self):
        """Stop monitoring VATSIM"""
        if self.monitoring:
            self.monitoring = False
            self.worker.stop()

            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)

            self.tray_icon.setIcon(self.create_icon("gray"))
            self.tray_icon.showMessage(
                "VATSIM Monitor Stopped",
                "No longer monitoring KOAK tower",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            logging.info("Stopped VATSIM monitoring")

    def force_check(self):
        """Force an immediate check"""
        if self.monitoring:
            # Trigger a check by calling the worker method directly
            # This runs in a separate thread to avoid blocking the UI
            check_thread = threading.Thread(
                target=self.worker.check_tower_status, daemon=True
            )
            check_thread.start()
        else:
            self.tray_icon.showMessage(
                "Monitor Not Running",
                "Start monitoring first",
                QSystemTrayIcon.MessageIcon.Warning,
                2000,
            )

    def show_status(self):
        """Show status dialog"""
        dialog = StatusDialog(
            self.tower_online, self.controller_info, self.last_check, None
        )
        dialog.exec()

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.worker.check_interval, None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.worker.set_interval(dialog.new_interval)
            logging.info(f"Check interval updated to {dialog.new_interval} seconds")

            self.tray_icon.showMessage(
                "Settings Updated",
                f"Check interval set to {dialog.new_interval} seconds",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def quit_application(self):
        """Quit the application"""
        logging.info("Shutting down VATSIM Monitor...")

        # Prevent multiple shutdown attempts
        if self._shutting_down:
            return
        self._shutting_down = True

        # Stop monitoring and wait for worker thread to finish
        if self.monitoring:
            self.worker.stop()

        # Hide and clean up tray icon
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
            self.tray_icon.deleteLater()

        # Stop the signal timer
        if hasattr(self, "signal_timer"):
            self.signal_timer.stop()
            self.signal_timer.deleteLater()

        # Release instance lock
        release_instance_lock()

        # Process any remaining events to ensure cleanup
        self.processEvents()

        # Quit the application gracefully
        self.quit()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logging.info("Received Ctrl+C, shutting down gracefully...")
    release_instance_lock()
    sys.exit(0)


def main():
    """Main entry point"""
    # Check for existing instance
    if not acquire_instance_lock():
        print("Another instance of VATSIM Monitor is already running.")
        logging.info("Another instance detected, exiting...")
        sys.exit(0)

    # Register cleanup function to release lock on exit
    atexit.register(release_instance_lock)

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    try:
        app = VATSIMMonitor(sys.argv)

        logging.info("Starting VATSIM KOAK Tower Monitor...")

        # Start monitoring automatically
        app.start_monitoring()

        # Run the application
        sys.exit(app.exec())

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
        release_instance_lock()
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        release_instance_lock()
        sys.exit(1)


if __name__ == "__main__":
    main()
