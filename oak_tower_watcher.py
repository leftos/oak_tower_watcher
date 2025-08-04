#!/usr/bin/env python3
"""
VATSIM Tower Monitor
A system tray application that monitors VATSIM for tower controllers.
Uses Qt for cross-platform GUI components.
"""

import requests
import json
from datetime import datetime
import sys
import signal
import logging
import os
import atexit
import vlc
import re
from bs4 import BeautifulSoup, Tag

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
from PyQt6.QtCore import (
    QThread,
    pyqtSignal,
    Qt,
    QTimer,
    QPropertyAnimation,
    QRect,
    QEasingCurve,
)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QBrush, QPen, QFont

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("vatsim_monitor.log"), logging.StreamHandler()],
)

# Global variable to store lock file handle
_lock_file = None


def load_config():
    """Load configuration from config.json file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    default_config = {
        "airport": {
            "code": "KOAK",
            "name": "Oakland International Airport",
            "display_name": "Oakland Main Facility",
        },
        "monitoring": {"check_interval": 60},
        "callsigns": {
            "main_facility": ["OAK_TWR", "OAK_1_TWR"],
            "supporting_above": ["NCT_APP", "OAK_36_CTR", "OAK_62_CTR"],
            "supporting_below": ["OAK_GND", "OAK_1_GND"],
        },
        "api": {
            "vatsim_url": "https://data.vatsim.net/v3/vatsim-data.json",
            "roster_url": "https://oakartcc.org/about/roster",
        },
        "notifications": {
            "sound_enabled": True,
            "sound_file": "ding.mp3",
            "toast_duration": 3000,
        },
    }

    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logging.info(f"Loaded configuration from {config_path}")
                return config
        else:
            logging.warning(f"Config file not found at {config_path}, using defaults")
            # Create default config file
            save_config(default_config)
            return default_config
    except Exception as e:
        logging.error(f"Error loading config file: {e}, using defaults")
        return default_config


def save_config(config):
    """Save configuration to config.json file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            logging.info(f"Saved configuration to {config_path}")
    except Exception as e:
        logging.error(f"Error saving config file: {e}")


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

    status_updated = pyqtSignal(
        str, dict, dict, list
    )  # status, main_facility_info, supporting_above_info, supporting_below_controllers
    force_check_completed = pyqtSignal(
        str, dict, dict, list
    )  # status, main_facility_info, supporting_above_info, supporting_below_controllers
    error_occurred = pyqtSignal(str)
    force_check_requested = pyqtSignal()  # Signal to request immediate check

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.running = False
        self.config = config
        self.check_interval = config.get("monitoring", {}).get("check_interval", 60)
        self.force_check_flag = False
        self.is_force_check = False

        # Load API endpoints from config
        api_config = config.get("api", {})
        self.vatsim_api_url = api_config.get(
            "vatsim_url", "https://data.vatsim.net/v3/vatsim-data.json"
        )

        # Load callsigns from config
        callsigns = config.get("callsigns", {})
        self.main_facility_callsigns = callsigns.get("main_facility", ["OAK_TWR", "OAK_1_TWR"])
        self.supporting_above_callsigns = callsigns.get(
            "supporting_above", ["NCT_APP", "OAK_36_CTR", "OAK_62_CTR"]
        )
        self.supporting_below_callsigns = callsigns.get("supporting_below", ["OAK_GND", "OAK_1_GND"])

        # Connect the force check signal to the slot
        self.force_check_requested.connect(self.request_immediate_check)

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

            # Look for main facility controllers
            main_facility_controllers = []
            supporting_above_controllers = []
            supporting_below_controllers = []

            for controller in controllers:
                callsign = controller.get("callsign", "")

                # Check for main facility controllers
                if any(
                    main_facility_call in callsign.upper()
                    for main_facility_call in self.main_facility_callsigns
                ):
                    main_facility_controllers.append(controller)

                # Check for supporting above facility controllers
                elif any(
                    support_call in callsign.upper()
                    for support_call in self.supporting_above_callsigns
                ):
                    supporting_above_controllers.append(controller)

                # Check for supporting below controllers
                elif any(
                    supporting_below_call in callsign.upper()
                    for supporting_below_call in self.supporting_below_callsigns
                ):
                    supporting_below_controllers.append(controller)

            return main_facility_controllers, supporting_above_controllers, supporting_below_controllers

        except requests.exceptions.RequestException as e:
            logging.error(f"Error querying VATSIM API: {e}")
            self.error_occurred.emit(f"API Error: {str(e)}")
            return None, None, None
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing VATSIM API response: {e}")
            self.error_occurred.emit(f"JSON Error: {str(e)}")
            return None, None, None

    def check_main_facility_status(self):
        """Check if main facility is online"""
        main_facility_controllers, supporting_above_controllers, supporting_below_controllers = (
            self.query_vatsim_api()
        )

        if (
            main_facility_controllers is None
            and supporting_above_controllers is None
            and supporting_below_controllers is None
        ):
            # API error - don't change status
            return

        # Determine status based on what's online
        if main_facility_controllers and supporting_above_controllers:
            # Both main facility and supporting above facilities online - highest priority
            status = "main_facility_and_supporting_above_online"
            controller_info = main_facility_controllers[0]  # Use first controller found
            supporting_info = supporting_above_controllers[
                0
            ]  # Use first supporting above controller found
            logging.info(
                f"Main Facility AND Supporting Above Facility ONLINE: Main Facility: {controller_info['callsign']}, "
                f"Supporting Above: {supporting_info['callsign']}"
            )
        elif main_facility_controllers:
            # Main facility is online but no supporting above facilities
            status = "main_facility_online"
            controller_info = main_facility_controllers[0]  # Use first controller found
            supporting_info = {}
            logging.info(
                f"Main Facility ONLINE: {controller_info['callsign']} - {controller_info.get('name', 'Unknown')}"
            )
        elif supporting_above_controllers:
            # Main facility offline but supporting above facilities online
            status = "supporting_above_online"
            controller_info = {}
            supporting_info = supporting_above_controllers[
                0
            ]  # Use first supporting above controller found
            logging.info(
                f"Main Facility OFFLINE but supporting above facility ONLINE: "
                f"{supporting_info['callsign']} - {supporting_info.get('name', 'Unknown')}"
            )
        else:
            # Everything offline
            status = "all_offline"
            controller_info = {}
            supporting_info = {}
            logging.info("Main facility and supporting above facilities OFFLINE")

        if self.is_force_check:
            self.force_check_completed.emit(
                status, controller_info, supporting_info, supporting_below_controllers
            )
            self.is_force_check = False
        else:
            self.status_updated.emit(
                status, controller_info, supporting_info, supporting_below_controllers
            )

    def request_immediate_check(self):
        """Slot to handle force check requests"""
        self.force_check_flag = True
        self.is_force_check = True

    def run(self):
        """Main monitoring loop"""
        self.running = True
        while self.running:
            try:
                self.check_main_facility_status()

                # Sleep in small intervals to allow quick response to stop signals and force checks
                sleep_time = self.check_interval * 1000  # Convert to milliseconds
                sleep_chunk = 500  # Sleep in 500ms chunks

                while sleep_time > 0 and self.running:
                    # Check if force check was requested
                    if self.force_check_flag:
                        self.force_check_flag = False
                        logging.info("Force check requested, breaking sleep cycle")
                        break

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
                    # Check if force check was requested during error recovery too
                    if self.force_check_flag:
                        self.force_check_flag = False
                        logging.info(
                            "Force check requested during error recovery, breaking sleep cycle"
                        )
                        break

                    chunk_size = min(sleep_chunk, sleep_time)
                    self.msleep(chunk_size)
                    sleep_time -= chunk_size

    def stop(self):
        """Stop the worker thread"""
        self.running = False
        self.quit()
        # Wait for thread to finish - should be quick now with chunked sleep
        self.wait(2000)  # 2 second timeout should be plenty


class CustomToast(QDialog):
    """Custom toast notification widget with multiline support"""

    def __init__(
        self, title, message, toast_type="success", duration=3000, parent=None
    ):
        super().__init__(parent)
        self.duration = duration
        self.toast_type = toast_type

        # Set window properties
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setModal(False)

        # Setup UI
        self.setup_ui(title, message)
        self.position_toast()

        # Setup animation
        self.setup_animation()

        # Auto-hide timer
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_toast)

    def setup_ui(self, title, message):
        """Setup the toast UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)

        # Title label
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: black;")
        layout.addWidget(title_label)

        # Message label (supports multiline)
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: black; font-size: 10pt;")
        layout.addWidget(message_label)

        self.setLayout(layout)

        # Set background color based on type
        if self.toast_type == "success":
            bg_color = "rgb(76, 175, 80)"  # Green
        elif self.toast_type == "warning":
            bg_color = "rgb(255, 152, 0)"  # Orange
        elif self.toast_type == "error":
            bg_color = "rgb(244, 67, 54)"  # Red
        else:  # info
            bg_color = "rgb(33, 150, 243)"  # Blue

        self.setStyleSheet(
            f"""
            CustomToast {{
                background-color: {bg_color};
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 100);
            }}
        """
        )

        # Set fixed width and adjust height based on content
        self.setFixedWidth(320)
        self.adjustSize()

    def position_toast(self):
        """Position toast in bottom-right corner of screen"""
        from PyQt6.QtWidgets import QApplication

        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            screen = primary_screen.availableGeometry()
            toast_width = self.width()
            toast_height = self.height()

            x = screen.width() - toast_width - 20
            y = screen.height() - toast_height - 20

            self.move(x, y)
        else:
            # Fallback positioning
            self.move(100, 100)

    def setup_animation(self):
        """Setup slide-in animation"""
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_toast(self):
        """Show the toast with animation"""
        # Start position (off-screen to the right)
        from PyQt6.QtWidgets import QApplication

        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            screen = primary_screen.availableGeometry()
            start_x = screen.width()
            end_x = screen.width() - self.width() - 20
            y = screen.height() - self.height() - 20

            start_rect = QRect(start_x, y, self.width(), self.height())
            end_rect = QRect(end_x, y, self.width(), self.height())

            self.setGeometry(start_rect)
            self.show()

            # Animate slide-in
            self.animation.setStartValue(start_rect)
            self.animation.setEndValue(end_rect)
            self.animation.start()
        else:
            # Fallback - just show without animation
            self.show()

        # Start hide timer
        self.hide_timer.start(self.duration)

    def hide_toast(self):
        """Hide the toast with animation"""
        from PyQt6.QtWidgets import QApplication

        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            screen = primary_screen.availableGeometry()
            start_x = screen.width() - self.width() - 20
            end_x = screen.width()
            y = screen.height() - self.height() - 20

            start_rect = QRect(start_x, y, self.width(), self.height())
            end_rect = QRect(end_x, y, self.width(), self.height())

            self.animation.finished.connect(self.close)
            self.animation.setStartValue(start_rect)
            self.animation.setEndValue(end_rect)
            self.animation.start()
        else:
            # Fallback - just close
            self.close()


class StatusDialog(QDialog):
    """Dialog to show current main facility status"""

    def __init__(
        self,
        status,
        controller_info,
        supporting_info,
        supporting_below_controllers,
        last_check,
        display_name="Main Facility",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"{display_name} Status")
        self.setFixedSize(450, 350)

        layout = QVBoxLayout()

        # Status header
        if status == "main_facility_and_supporting_above_online":
            status_text = "ONLINE (Full Coverage)"
            color = "🟣"
        elif status == "main_facility_online":
            status_text = "ONLINE"
            color = "🟢"
        elif status == "supporting_above_online":
            status_text = "OFFLINE (Supporting Above Online)"
            color = "🟡"
        else:  # all_offline
            status_text = "OFFLINE"
            color = "🔴"

        status_label = QLabel(f"{color} {display_name}: {status_text}")
        status_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)

        # Controller details
        details_text = QTextEdit()
        details_text.setReadOnly(True)

        # Helper function to format supporting below controllers for status dialog
        def format_supporting_below_controllers_details(supporting_below_controllers):
            if not supporting_below_controllers:
                return ""

            supporting_below_details = "\n\nSupporting Below Controllers:"
            for supporting_below in supporting_below_controllers:
                supporting_below_details += f"""
Callsign: {supporting_below.get('callsign', 'Unknown')}
Name: {supporting_below.get('name', 'Unknown')}
Frequency: {supporting_below.get('frequency', 'Unknown')}
Rating: {supporting_below.get('rating', 'Unknown')}
Logon Time: {supporting_below.get('logon_time', 'Unknown')}
Server: {supporting_below.get('server', 'Unknown')}"""
            return supporting_below_details

        supporting_below_details = format_supporting_below_controllers_details(supporting_below_controllers)

        if (
            status == "main_facility_and_supporting_above_online"
            and controller_info
            and supporting_info
        ):
            details = f"""Main Facility Controller Information:

Callsign: {controller_info.get('callsign', 'Unknown')}
Name: {controller_info.get('name', 'Unknown')}
Frequency: {controller_info.get('frequency', 'Unknown')}
Rating: {controller_info.get('rating', 'Unknown')}
Logon Time: {controller_info.get('logon_time', 'Unknown')}
Server: {controller_info.get('server', 'Unknown')}

Supporting Above Facility Information:
Callsign: {supporting_info.get('callsign', 'Unknown')}
Name: {supporting_info.get('name', 'Unknown')}
Frequency: {supporting_info.get('frequency', 'Unknown')}
Rating: {supporting_info.get('rating', 'Unknown')}
Logon Time: {supporting_info.get('logon_time', 'Unknown')}
Server: {supporting_info.get('server', 'Unknown')}{supporting_below_details}"""

        elif status == "main_facility_online" and controller_info:
            details = f"""Main Facility Controller Information:

Callsign: {controller_info.get('callsign', 'Unknown')}
Name: {controller_info.get('name', 'Unknown')}
Frequency: {controller_info.get('frequency', 'Unknown')}
Rating: {controller_info.get('rating', 'Unknown')}
Logon Time: {controller_info.get('logon_time', 'Unknown')}
Server: {controller_info.get('server', 'Unknown')}{supporting_below_details}"""

        elif status == "supporting_above_online" and supporting_info:
            details = f"""Main Facility Controller: OFFLINE

Supporting Above Facility Online:
Callsign: {supporting_info.get('callsign', 'Unknown')}
Name: {supporting_info.get('name', 'Unknown')}
Frequency: {supporting_info.get('frequency', 'Unknown')}
Rating: {supporting_info.get('rating', 'Unknown')}
Logon Time: {supporting_info.get('logon_time', 'Unknown')}
Server: {supporting_info.get('server', 'Unknown')}{supporting_below_details}"""
        else:
            details = (
                f"No main facility or supporting above controllers currently online.{supporting_below_details}"
            )

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

        # Load configuration
        self.config = load_config()

        # Get airport configuration
        self.airport_config = self.config.get("airport", {})
        self.airport_code = self.airport_config.get("code", "KOAK")
        self.airport_name = self.airport_config.get(
            "name", "Oakland International Airport"
        )
        self.display_name = self.airport_config.get(
            "display_name", f"{self.airport_code} Main Facility"
        )

        # Application state
        self.main_facility_online = False
        self.controller_info = {}
        self.last_check = None
        self.monitoring = False
        self._shutting_down = False

        # Controller name lookup dictionary
        self.controller_names = {}

        # Load ARTCC roster at startup
        self.load_roster()

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
        elif color == "yellow":
            brush = QBrush(Qt.GlobalColor.yellow)
        elif color == "purple":
            brush = QBrush(Qt.GlobalColor.magenta)  # Using magenta for purple
        else:  # gray
            brush = QBrush(Qt.GlobalColor.gray)

        painter.setBrush(brush)
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()

        return QIcon(pixmap)

    def load_roster(self):
        """Load ARTCC roster to translate CIDs to real names"""
        try:
            logging.info("Loading ARTCC roster...")
            roster_url = self.config.get("api", {}).get(
                "roster_url", "https://oakartcc.org/about/roster"
            )
            response = requests.get(roster_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Look for controller information in the roster
            # Try to find tables or structured data containing CID and names
            tables = soup.find_all("table")
            for table in tables:
                if isinstance(table, Tag):
                    rows = table.find_all("tr")
                    for row in rows:
                        if isinstance(row, Tag):
                            cells = row.find_all(["td", "th"])
                        else:
                            continue
                else:
                    continue
                    if len(cells) >= 2:
                        # Look for patterns that might be CID (numeric) and name
                        for i, cell in enumerate(cells):
                            text = cell.get_text(strip=True)
                            # Check if this looks like a CID (numeric ID)
                            if (
                                text.isdigit() and len(text) >= 6
                            ):  # CIDs are typically 6+ digits
                                cid = text
                                # Look for name in adjacent cells
                                for j in range(max(0, i - 2), min(len(cells), i + 3)):
                                    if j != i:
                                        name_text = cells[j].get_text(strip=True)
                                        # Skip if it's also numeric or empty
                                        if (
                                            name_text
                                            and not name_text.isdigit()
                                            and len(name_text) > 2
                                        ):
                                            # Clean up the name (remove extra whitespace, etc.)
                                            clean_name = re.sub(
                                                r"\s+", " ", name_text
                                            ).strip()
                                            if clean_name and not any(
                                                char.isdigit()
                                                for char in clean_name[:3]
                                            ):
                                                # Convert name format to "firstname lastname"
                                                formatted_name = (
                                                    self.format_controller_name(
                                                        clean_name
                                                    )
                                                )
                                                self.controller_names[cid] = (
                                                    formatted_name
                                                )
                                                break

            # Also try to find div elements or other structures with controller info
            # Look for patterns like "John Doe - 1234567" or similar
            text_content = soup.get_text()
            # Pattern to match name followed by CID or CID followed by name
            patterns = [
                r"([A-Za-z\s]{3,30})\s*[-–]\s*(\d{6,})",  # Name - CID
                r"(\d{6,})\s*[-–]\s*([A-Za-z\s]{3,30})",  # CID - Name
            ]

            for pattern in patterns:
                matches = re.findall(pattern, text_content)
                for match in matches:
                    if match[0].isdigit():  # First group is CID
                        cid, name = match[0], match[1].strip()
                    else:  # First group is name
                        name, cid = match[0].strip(), match[1]

                    # Clean up the name
                    clean_name = re.sub(r"\s+", " ", name).strip()
                    if clean_name and len(clean_name) > 2:
                        # Convert name format to "firstname lastname"
                        formatted_name = self.format_controller_name(clean_name)
                        self.controller_names[cid] = formatted_name

            logging.info(
                f"Loaded {len(self.controller_names)} controller names from ARTCC roster"
            )
            if self.controller_names:
                logging.debug(
                    f"Sample entries: {dict(list(self.controller_names.items())[:3])}"
                )

        except Exception as e:
            logging.warning(f"Could not load ARTCC roster: {e}")
            self.controller_names = {}

    def format_controller_name(self, name):
        """Convert 'lastname, firstname(operatinginitials)' to 'firstname lastname'"""
        # Check if the name matches the pattern "lastname, firstname(operatinginitials)"
        match = re.match(r"^([^,]+),\s*([^(]+)(?:\([^)]*\))?", name)
        if match:
            lastname = match.group(1).strip()
            firstname = match.group(2).strip()
            return f"{firstname} {lastname}"

        # If it doesn't match the pattern, return the original name
        return name

    def get_controller_name(self, controller_info):
        """Get the real name of a controller, using roster lookup if needed"""
        # First try the name from VATSIM data
        vatsim_name = controller_info.get("name", "").strip()

        # If VATSIM name exists and doesn't look like just a number, use it
        if vatsim_name and not vatsim_name.isdigit() and len(vatsim_name) > 2:
            return vatsim_name

        # Otherwise, try to look up by CID in our roster
        cid = str(controller_info.get("cid", ""))
        if cid in self.controller_names:
            return self.controller_names[cid]

        # Fallback to VATSIM name or "Unknown Controller"
        return vatsim_name if vatsim_name else "Unknown Controller"

    def format_supporting_below_controllers_info(self, supporting_below_controllers):
        """Format supporting below controllers information for display"""
        if not supporting_below_controllers:
            return ""

        supporting_below_info = []
        for supporting_below in supporting_below_controllers:
            callsign = supporting_below.get("callsign", "Unknown")
            name = self.get_controller_name(supporting_below)
            supporting_below_info.append(f"{callsign} ({name})")

        if len(supporting_below_info) == 1:
            return f"\nSupporting Below: {supporting_below_info[0]}"
        else:
            return f"\nSupporting Below: {', '.join(supporting_below_info)}"

    def get_transition_notification(
        self,
        previous_status,
        current_status,
        controller_info,
        supporting_info,
        supporting_below_controllers,
    ):
        """Generate appropriate notification message based on state transition"""

        # Get supporting below controller info for all messages
        supporting_below_info = self.format_supporting_below_controllers_info(supporting_below_controllers)

        # Handle transitions to full coverage
        if current_status == "main_facility_and_supporting_above_online":
            main_facility_callsign = controller_info.get("callsign", "Unknown")
            main_facility_name = self.get_controller_name(controller_info)
            support_callsign = supporting_info.get("callsign", "Unknown")
            support_name = self.get_controller_name(supporting_info)
            message = (
                f"Main Facility: {main_facility_callsign} ({main_facility_name})\n"
                f"Supporting Above: {support_callsign} ({support_name}){supporting_below_info}"
            )

            if previous_status == "main_facility_online":
                title = "Supporting Above Facilities Now Online!"
                return title, message, "success"
            elif previous_status == "supporting_above_online":
                title = "Main Facility Now Online!"
                return title, message, "success"
            else:  # from all_offline
                title = "Full Coverage Online!"
                return title, message, "success"

        # Handle transitions to main facility only
        elif current_status == "main_facility_online":
            callsign = controller_info.get("callsign", "Unknown")
            controller_name = self.get_controller_name(controller_info)

            if previous_status == "main_facility_and_supporting_above_online":
                title = "Supporting Above Facilities Now Offline"
                message = f"Only main facility remains online\n{callsign} ({controller_name}){supporting_below_info}"
                return title, message, "warning"
            elif previous_status == "supporting_above_online":
                title = "Main Facility Now Online!"
                message = (
                    f"Main facility controller is now online\n{callsign} ({controller_name}){supporting_below_info}"
                )
                return title, message, "success"
            else:  # from all_offline
                title = f"{self.display_name} Online!"
                message = f"{callsign} is now online!\nController: {controller_name}{supporting_below_info}"
                return title, message, "success"

        # Handle transitions to supporting above only
        elif current_status == "supporting_above_online":
            callsign = supporting_info.get("callsign", "Unknown")
            controller_name = self.get_controller_name(supporting_info)

            if previous_status == "main_facility_and_supporting_above_online":
                title = "Main Facility Now Offline"
                message = (
                    f"Only supporting above facility remains online\n"
                    f"{callsign} ({controller_name}){supporting_below_info}"
                )
                return title, message, "warning"
            elif previous_status == "main_facility_online":
                title = "Main Facility Now Offline"
                message = (
                    f"Main facility went offline, but {callsign} is online\n"
                    f"Controller: {controller_name}{supporting_below_info}"
                )
                return title, message, "warning"
            else:  # from all_offline
                title = "Supporting Above Facility Online"
                message = (
                    f"Main facility offline, but {callsign} is online\n"
                    f"Controller: {controller_name}{supporting_below_info}"
                )
                return title, message, "warning"

        # Handle transitions to all offline
        else:  # all_offline
            if previous_status == "main_facility_and_supporting_above_online":
                title = "All Facilities Now Offline"
                message = (
                    f"Both main facility and supporting above controllers have gone offline{supporting_below_info}"
                )
            elif previous_status == "main_facility_online":
                title = "Main Facility Now Offline"
                message = f"Main facility controller has gone offline{supporting_below_info}"
            elif previous_status == "supporting_above_online":
                title = "Supporting Above Facility Now Offline"
                message = f"Supporting above controller has gone offline{supporting_below_info}"
            else:
                title = "All Facilities Offline"
                message = (
                    f"No main facility or supporting above controllers found{supporting_below_info}"
                )

            return title, message, "error"

    def play_notification_sound(self):
        """Play the custom notification sound"""
        try:
            # Check if sound is enabled in config
            notifications_config = self.config.get("notifications", {})
            if not notifications_config.get("sound_enabled", True):
                return

            sound_file = notifications_config.get("sound_file", "ding.mp3")
            sound_path = os.path.join(os.path.dirname(__file__), sound_file)
            if os.path.exists(sound_path):
                if not hasattr(self, "_vlc_instance") or self._vlc_instance is None:
                    self._vlc_instance = vlc.Instance()
                    if self._vlc_instance is not None:
                        self._vlc_player = self._vlc_instance.media_player_new()

                if self._vlc_instance is not None:
                    media = self._vlc_instance.media_new(sound_path)
                    if hasattr(self, "_vlc_player") and self._vlc_player is not None:
                        self._vlc_player.set_media(media)
                        self._vlc_player.play()
            else:
                logging.warning(f"Sound file not found: {sound_path}")
        except Exception as e:
            logging.error(f"Error playing notification sound: {e}")

    def show_toast_notification(
        self, title, message, toast_type="success", duration=None
    ):
        """Show a custom toast notification with sound"""
        try:
            # Use duration from config if not specified
            if duration is None:
                duration = self.config.get("notifications", {}).get(
                    "toast_duration", 3000
                )

            # Play custom sound
            self.play_notification_sound()

            # Show custom toast notification
            toast = CustomToast(title, message, toast_type, duration)
            toast.show_toast()

        except Exception as e:
            logging.error(f"Error showing toast notification: {e}")
            # Fallback to system tray notification if toast fails
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration or 3000,
            )

    def setup_tray_icon(self):
        """Setup system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_icon("gray"))
        self.update_tray_tooltip()

        # Create menu
        tray_menu = QMenu()

        # Status action
        status_action = QAction(f"{self.display_name} Status", self)
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
        self.worker = VATSIMWorker(self.config)
        self.worker.status_updated.connect(self.on_status_updated)
        self.worker.force_check_completed.connect(self.on_force_check_completed)
        self.worker.error_occurred.connect(self.on_error)

        # Add supporting above facility info and supporting below controllers
        self.supporting_info = {}
        self.supporting_below_controllers = []
        self.current_status = "all_offline"

    def update_tray_tooltip(self):
        """Update the system tray icon tooltip with current status"""
        if not hasattr(self, "current_status"):
            self.tray_icon.setToolTip(
                f"VATSIM {self.display_name} Monitor - Starting..."
            )
            return

        if self.current_status == "main_facility_and_supporting_above_online":
            if hasattr(self, "controller_info") and hasattr(self, "supporting_info"):
                main_facility_callsign = self.controller_info.get("callsign", "Unknown")
                main_facility_name = self.get_controller_name(self.controller_info)
                support_callsign = self.supporting_info.get("callsign", "Unknown")
                support_name = self.get_controller_name(self.supporting_info)
                tooltip = (
                    f"{self.display_name}: ONLINE (Full Coverage)\n"
                    f"Main Facility: {main_facility_callsign} ({main_facility_name})\n"
                    f"Supporting Above: {support_callsign} ({support_name})"
                )
            else:
                tooltip = f"{self.display_name}: ONLINE (Full Coverage)"
        elif self.current_status == "main_facility_online":
            if hasattr(self, "controller_info") and self.controller_info:
                main_facility_callsign = self.controller_info.get("callsign", "Unknown")
                main_facility_name = self.get_controller_name(self.controller_info)
                tooltip = f"{self.display_name}: ONLINE\nController: {main_facility_callsign} ({main_facility_name})"
            else:
                tooltip = f"{self.display_name}: ONLINE"
        elif self.current_status == "supporting_above_online":
            if hasattr(self, "supporting_info") and self.supporting_info:
                support_callsign = self.supporting_info.get("callsign", "Unknown")
                support_name = self.get_controller_name(self.supporting_info)
                tooltip = f"{self.display_name}: OFFLINE\nSupporting Above: {support_callsign} ({support_name}) ONLINE"
            else:
                tooltip = f"{self.display_name}: OFFLINE (Supporting Above Online)"
        else:  # all_offline
            tooltip = f"{self.display_name}: OFFLINE"

        # Add supporting below controller info if available
        if hasattr(self, "supporting_below_controllers") and self.supporting_below_controllers:
            supporting_below_info = []
            for sbc in self.supporting_below_controllers:
                callsign = sbc.get("callsign", "Unknown")
                name = self.get_controller_name(sbc)
                supporting_below_info.append(f"{callsign} ({name})")

            if len(supporting_below_info) == 1:
                tooltip += f"\nSupporting Below: {supporting_below_info[0]}"
            elif len(supporting_below_info) > 1:
                tooltip += f"\nSupporting Below: {', '.join(supporting_below_info)}"

        self.tray_icon.setToolTip(tooltip)

    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_status()

    def on_status_updated(
        self, status, controller_info, supporting_info, supporting_below_controllers
    ):
        """Handle status update from worker thread"""
        previous_status = self.current_status
        self.current_status = status
        self.main_facility_online = status == "main_facility_online"
        self.controller_info = controller_info
        self.supporting_info = supporting_info
        self.supporting_below_controllers = supporting_below_controllers
        self.last_check = datetime.now()

        # Update tray icon based on status
        if status == "main_facility_and_supporting_above_online":
            color = "purple"
        elif status == "main_facility_online":
            color = "green"
        elif status == "supporting_above_online":
            color = "yellow"
        else:  # all_offline
            color = "red"

        self.tray_icon.setIcon(self.create_icon(color))

        # Update tooltip with current status
        self.update_tray_tooltip()

        # Show notification if status changed
        if status != previous_status:
            title, message, toast_type = self.get_transition_notification(
                previous_status,
                status,
                controller_info,
                supporting_info,
                supporting_below_controllers,
            )
            self.show_toast_notification(title, message, toast_type, 3000)

    def on_force_check_completed(
        self, status, controller_info, supporting_info, supporting_below_controllers
    ):
        """Handle force check completion - always show notification"""
        # Update internal state
        self.current_status = status
        self.main_facility_online = status == "main_facility_online"
        self.controller_info = controller_info
        self.supporting_info = supporting_info
        self.supporting_below_controllers = supporting_below_controllers
        self.last_check = datetime.now()

        # Update tray icon based on status
        if status == "main_facility_and_supporting_above_online":
            color = "purple"
        elif status == "main_facility_online":
            color = "green"
        elif status == "supporting_above_online":
            color = "yellow"
        else:  # all_offline
            color = "red"

        self.tray_icon.setIcon(self.create_icon(color))

        # Update tooltip with current status
        self.update_tray_tooltip()

        # Always show notification for force checks
        supporting_below_info = self.format_supporting_below_controllers_info(supporting_below_controllers)

        if status == "main_facility_and_supporting_above_online":
            main_facility_callsign = controller_info.get("callsign", "Unknown")
            main_facility_name = self.get_controller_name(controller_info)
            support_callsign = supporting_info.get("callsign", "Unknown")
            support_name = self.get_controller_name(supporting_info)
            message = (
                f"Main Facility: {main_facility_callsign} ({main_facility_name})\n"
                f"Supporting Above: {support_callsign} ({support_name}){supporting_below_info}"
            )
            self.show_toast_notification(
                f"{self.display_name} Status", message, "success", 3000
            )
        elif status == "main_facility_online":
            callsign = controller_info.get("callsign", "Unknown")
            controller_name = self.get_controller_name(controller_info)
            message = (
                f"{callsign} is online\nController: {controller_name}{supporting_below_info}"
            )
            self.show_toast_notification(
                f"{self.display_name} Status", message, "success", 3000
            )
        elif status == "supporting_above_online":
            callsign = supporting_info.get("callsign", "Unknown")
            controller_name = self.get_controller_name(supporting_info)
            message = (
                f"Main facility offline, but {callsign} is online\n"
                f"Controller: {controller_name}{supporting_below_info}"
            )
            self.show_toast_notification(
                f"{self.display_name} Status", message, "warning", 3000
            )
        else:  # all_offline
            message = f"No controllers found{supporting_below_info}"
            self.show_toast_notification(
                f"{self.display_name} Status", message, "info", 3000
            )

    def on_error(self, error_message):
        """Handle error from worker thread"""
        logging.error(error_message)
        self.tray_icon.setIcon(self.create_icon("gray"))
        self.tray_icon.setToolTip(f"VATSIM {self.display_name} Monitor - Error")

    def start_monitoring(self):
        """Start monitoring VATSIM"""
        if not self.monitoring:
            self.monitoring = True
            self.worker.start()

            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)

            # self.tray_icon.showMessage(
            #     "VATSIM Monitor Started",
            #     "Monitoring KOAK main facility status",
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
            self.tray_icon.setToolTip(f"VATSIM {self.display_name} Monitor - Stopped")
            # self.tray_icon.showMessage(
            #     "VATSIM Monitor Stopped",
            #     "No longer monitoring KOAK main facility",
            #     QSystemTrayIcon.MessageIcon.Information,
            #     2000,
            # )
            logging.info("Stopped VATSIM monitoring")

    def force_check(self):
        """Force an immediate check"""
        if self.monitoring:
            # Signal the worker thread to perform an immediate check
            logging.info("Requesting immediate check...")
            self.worker.force_check_requested.emit()
        else:
            self.show_toast_notification(
                "Monitor Not Running", "Start monitoring first", "warning", 2000
            )

    def show_status(self):
        """Show status dialog"""
        dialog = StatusDialog(
            self.current_status,
            self.controller_info,
            self.supporting_info,
            self.supporting_below_controllers,
            self.last_check,
            self.display_name,
            None,
        )
        dialog.exec()

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.worker.check_interval, None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.worker.set_interval(dialog.new_interval)

            # Update config and save it
            self.config["monitoring"]["check_interval"] = dialog.new_interval
            save_config(self.config)

            logging.info(f"Check interval updated to {dialog.new_interval} seconds")

            self.show_toast_notification(
                "Settings Updated",
                f"Check interval set to {dialog.new_interval} seconds",
                "success",
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

        logging.info(f"Starting VATSIM {app.display_name} Monitor...")

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
