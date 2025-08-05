#!/usr/bin/env python3
"""
Main Application module for VATSIM Tower Monitor
Contains the main VATSIMMonitor application class with system tray functionality.
"""

import os
import sys
import logging
import vlc
from datetime import datetime
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QMessageBox,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QBrush, QPen, QColor
from PyQt6.QtCore import Qt

from config import load_config, save_config
from utils import (
    darken_color_for_notification,
    load_artcc_roster,
    get_controller_name,
    get_controller_initials,
)
from vatsim_worker import VATSIMWorker
from gui_components import CustomToast, StatusDialog, SettingsDialog


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

        # Initialize cached icons
        self.initialize_cached_icons()

    def get_status_colors(self, status):
        """Get both tray icon and notification colors for a given status"""
        # Get colors from config
        colors_config = self.config.get("colors", {})
        notification_colors = colors_config.get("notifications", {})

        # Map status to color names for tray icons
        status_to_color_name = {
            "main_facility_and_supporting_above_online": "purple",
            "main_facility_online": "green",
            "supporting_above_online": "yellow",
            "all_offline": "red",
            "error": "gray",
        }

        # Get the notification color from config
        notification_color_str = notification_colors.get(status, notification_colors.get("error", "rgb(64, 64, 64)"))

        # Parse RGB string to extract values for darkening
        import re
        rgb_match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', notification_color_str)
        if rgb_match:
            rgb_values = [int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))]
            notification_color = darken_color_for_notification(rgb_values)
        else:
            # Fallback if parsing fails
            notification_color = notification_color_str

        return {
            "tray": status_to_color_name.get(status, "gray"),
            "notification": notification_color,
        }

    def colorize_airport_tower(self, color_rgb, brightness=1.2):
        """
        Colorize the airport tower icon to the specified RGB color.

        Args:
            color_rgb: Tuple of (R, G, B) values (0-255)
            brightness: Brightness multiplier (1.0 = normal, >1.0 = brighter)

        Returns:
            QIcon: Colorized airport tower icon
        """
        try:
            # Load the original airport tower image
            tower_path = os.path.join(os.path.dirname(__file__), "airport-tower.png")
            if not os.path.exists(tower_path):
                logging.warning(
                    f"Airport tower icon not found at {tower_path}, falling back to circle"
                )
                return self.create_circle_icon(color_rgb)

            # Open and process the image
            pil_img = Image.open(tower_path).convert("RGBA")

            # Create a new image with the same size
            colored_img = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))

            # Process each pixel
            for y in range(pil_img.height):
                for x in range(pil_img.width):
                    pixel = pil_img.getpixel((x, y))

                    # Handle different pixel formats
                    if isinstance(pixel, tuple):
                        if len(pixel) == 4:
                            r, g, b, a = pixel
                        elif len(pixel) == 3:
                            r, g, b = pixel
                            a = 255  # Fully opaque
                        else:
                            continue  # Skip invalid pixels
                    else:
                        # Handle single channel or other formats
                        continue

                    # If pixel is not transparent
                    if a > 0:
                        # Calculate brightness of original pixel (for anti-aliasing edges)
                        original_brightness = (r + g + b) / 3 / 255.0

                        # Apply the new color while preserving alpha and edge smoothing
                        new_r = int(
                            color_rgb[0] * brightness * (1 - original_brightness)
                        )
                        new_g = int(
                            color_rgb[1] * brightness * (1 - original_brightness)
                        )
                        new_b = int(
                            color_rgb[2] * brightness * (1 - original_brightness)
                        )

                        # Clamp values to 0-255
                        new_r = max(0, min(255, new_r))
                        new_g = max(0, min(255, new_g))
                        new_b = max(0, min(255, new_b))

                        colored_img.putpixel((x, y), (new_r, new_g, new_b, a))
                    else:
                        # Keep transparent pixels transparent
                        colored_img.putpixel((x, y), (0, 0, 0, 0))

            # Convert PIL image to QPixmap
            import io

            img_bytes = io.BytesIO()
            colored_img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes.getvalue())

            return QIcon(pixmap)

        except Exception as e:
            logging.error(f"Error colorizing airport tower icon: {e}")
            return self.create_circle_icon(color_rgb)

    def create_circle_icon(self, color_rgb):
        """Fallback method to create a colored circle icon"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Convert RGB tuple to QBrush
        color = QColor(color_rgb[0], color_rgb[1], color_rgb[2])
        brush = QBrush(color)

        painter.setBrush(brush)
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()

        return QIcon(pixmap)

    def create_icon(self, color="gray"):
        """Create a colored airport tower icon from cached versions"""
        # Return cached icon if available
        if hasattr(self, "_cached_icons") and color in self._cached_icons:
            return self._cached_icons[color]

        # Fallback to circle if no cached icons available - use config colors
        colors_config = self.config.get("colors", {})
        color_map = {
            "green": tuple(colors_config.get("main_facility_online", [0, 150, 0])),
            "red": tuple(colors_config.get("all_offline", [200, 0, 0])),
            "yellow": tuple(
                colors_config.get("supporting_above_online", [200, 150, 0])
            ),
            "purple": tuple(
                colors_config.get(
                    "main_facility_and_supporting_above_online", [128, 0, 128]
                )
            ),
            "gray": tuple(colors_config.get("error", [100, 100, 100])),
        }

        rgb_color = color_map.get(
            color, tuple(colors_config.get("error", [100, 100, 100]))
        )
        return self.create_circle_icon(rgb_color)

    def initialize_cached_icons(self):
        """Initialize and cache all colored versions of the airport tower icon"""
        logging.info("Initializing cached airport tower icons...")

        # Get colors from config using status-based color mapping
        colors_config = self.config.get("colors", {})

        # Define colors for different states with fallback defaults
        colors = {
            "green": tuple(
                colors_config.get("main_facility_online", [0, 150, 0])
            ),  # Main facility online
            "red": tuple(colors_config.get("all_offline", [200, 0, 0])),  # All offline
            "yellow": tuple(
                colors_config.get("supporting_above_online", [200, 150, 0])
            ),  # Supporting above online
            "purple": tuple(
                colors_config.get(
                    "main_facility_and_supporting_above_online", [128, 0, 128]
                )
            ),  # Full coverage
            "gray": tuple(
                colors_config.get("error", [100, 100, 100])
            ),  # Error/stopped state
        }

        self._cached_icons = {}

        for color_name, rgb_values in colors.items():
            try:
                self._cached_icons[color_name] = self.colorize_airport_tower(rgb_values)
                logging.debug(f"Cached {color_name} airport tower icon")
            except Exception as e:
                logging.error(f"Failed to create {color_name} icon: {e}")
                # Fallback to circle icon
                self._cached_icons[color_name] = self.create_circle_icon(rgb_values)

        logging.info(
            f"Successfully cached {len(self._cached_icons)} airport tower icons"
        )

    def load_roster(self):
        """Load ARTCC roster to translate CIDs to real names"""
        roster_url = self.config.get("api", {}).get(
            "roster_url", "https://oakartcc.org/about/roster"
        )
        self.controller_names = load_artcc_roster(roster_url)

    def format_supporting_below_controllers_info(self, supporting_below_controllers):
        """Format supporting below controllers information for display"""
        if not supporting_below_controllers:
            return ""

        supporting_below_info = []
        for supporting_below in supporting_below_controllers:
            callsign = supporting_below.get("callsign", "Unknown")
            name = get_controller_name(supporting_below, self.controller_names)
            supporting_below_info.append(f"{callsign} ({name})")

        if len(supporting_below_info) == 1:
            return f"\nSupporting Below: {supporting_below_info[0]}"
        else:
            return f"\nSupporting Below: {', '.join(supporting_below_info)}"

    def format_multiple_controllers_info(self, controllers, prefix=""):
        """Format multiple controllers information for display"""
        if not controllers:
            return ""

        if isinstance(controllers, dict):  # Handle legacy single controller format
            controllers = [controllers]

        controller_info = []
        for controller in controllers:
            callsign = controller.get("callsign", "Unknown")
            name = get_controller_name(controller, self.controller_names)
            controller_info.append(f"{callsign} ({name})")

        if len(controller_info) == 1:
            return f"{prefix}{controller_info[0]}"
        else:
            return f"{prefix}{', '.join(controller_info)}"

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
        supporting_below_info = self.format_supporting_below_controllers_info(
            supporting_below_controllers
        )

        # Handle transitions to full coverage
        if current_status == "main_facility_and_supporting_above_online":
            main_facility_info = self.format_multiple_controllers_info(
                controller_info, f"{self.display_name}: "
            )
            support_info = self.format_multiple_controllers_info(
                supporting_info, "Supporting Above: "
            )
            message = f"{main_facility_info}\n{support_info}{supporting_below_info}"

            if previous_status == "main_facility_online":
                title = "Supporting Above Facilities Now Online!"
                return title, message, "success"
            elif previous_status == "supporting_above_online":
                title = f"{self.display_name} Now Online!"
                return title, message, "success"
            else:  # from all_offline
                title = "Full Coverage Online!"
                return title, message, "success"

        # Handle transitions to main facility only
        elif current_status == "main_facility_online":
            main_facility_info = self.format_multiple_controllers_info(controller_info)

            if previous_status == "main_facility_and_supporting_above_online":
                title = "Supporting Above Facilities Now Offline"
                message = f"Only {self.display_name} remains online\n{main_facility_info}{supporting_below_info}"
                return title, message, "warning"
            elif previous_status == "supporting_above_online":
                title = f"{self.display_name} Now Online!"
                message = f"{self.display_name} controller is now online\n{main_facility_info}{supporting_below_info}"
                return title, message, "success"
            else:  # from all_offline
                title = f"{self.display_name} Online!"
                message = f"{main_facility_info} is now online!{supporting_below_info}"
                return title, message, "success"

        # Handle transitions to supporting above only
        elif current_status == "supporting_above_online":
            support_info = self.format_multiple_controllers_info(supporting_info)

            if previous_status == "main_facility_and_supporting_above_online":
                title = f"{self.display_name} Now Offline"
                message = (
                    f"Only supporting above facility remains online\n"
                    f"{support_info}{supporting_below_info}"
                )
                return title, message, "warning"
            elif previous_status == "main_facility_online":
                title = f"{self.display_name} Now Offline"
                message = f"{self.display_name} went offline, but {support_info} is online{supporting_below_info}"
                return title, message, "warning"
            else:  # from all_offline
                title = "Supporting Above Facility Online"
                message = f"{self.display_name} is offline, but {support_info} is online{supporting_below_info}"
                return title, message, "warning"

        # Handle transitions to all offline
        else:  # all_offline
            if previous_status == "main_facility_and_supporting_above_online":
                title = "All Facilities Now Offline"
                message = (
                    f"Both {self.display_name} and supporting above controllers have gone offline"
                    + f"{supporting_below_info}"
                )
            elif previous_status == "main_facility_online":
                title = f"{self.display_name} Now Offline"
                message = (
                    f"{self.display_name} controller has gone offline{supporting_below_info}"
                )
            elif previous_status == "supporting_above_online":
                title = "Supporting Above Facility Now Offline"
                message = f"Supporting above controller has gone offline{supporting_below_info}"
            else:
                title = "All Facilities Offline"
                message = f"No {self.display_name} or supporting above controllers found{supporting_below_info}"

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
        self, title, message, toast_type="success", duration=None, status=None
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

            # Get background color based on status if provided, or use toast type colors from config
            bg_color = None
            if status:
                colors = self.get_status_colors(status)
                bg_color = colors["notification"]

            # Show custom toast notification
            toast = CustomToast(title, message, toast_type, duration, bg_color)
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
            self.tray_icon.setToolTip(f"VATSIM {self.airport_code} - Starting...")
            return

        # Use airport code instead of full display name for brevity
        airport = self.airport_code

        if self.current_status == "main_facility_and_supporting_above_online":
            # Show first controller from each with initials
            main_text = self._format_controller_for_tooltip(self.controller_info, "Main")
            support_text = self._format_controller_for_tooltip(self.supporting_info, "Support")
            tooltip = f"{airport}: ONLINE (Full)\n{main_text}\n{support_text}"
        elif self.current_status == "main_facility_online":
            # Show main facility controller with initials
            controller_text = self._format_controller_for_tooltip(self.controller_info)
            tooltip = f"{airport}: ONLINE\n{controller_text}"
        elif self.current_status == "supporting_above_online":
            # Show supporting facility with initials
            support_text = self._format_controller_for_tooltip(self.supporting_info, "Support")
            tooltip = f"{airport}: OFFLINE\n{support_text}"
        else:  # all_offline
            tooltip = f"{airport}: OFFLINE"

        self.tray_icon.setToolTip(tooltip)

    def _format_controller_for_tooltip(self, controller_info, prefix=""):
        """Format controller info for tooltip display with operating initials"""
        if not controller_info:
            return f"{prefix}: None" if prefix else "None"

        # Handle both list and single controller formats
        controllers = controller_info if isinstance(controller_info, list) else [controller_info]
        
        if not controllers:
            return f"{prefix}: None" if prefix else "None"

        # Get first controller
        first_controller = controllers[0]
        callsign = first_controller.get("callsign", "Unknown")
        
        # Get operating initials from roster
        initials = get_controller_initials(first_controller, self.controller_names)
        
        # Format the display text
        if initials:
            controller_text = f"{callsign} ({initials})"
        else:
            controller_text = callsign
            
        # Add count if multiple controllers
        if len(controllers) > 1:
            controller_text += f" +{len(controllers)-1}"
            
        # Add prefix if provided
        if prefix:
            return f"{prefix}: {controller_text}"
        else:
            return controller_text

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
        self.main_facility_online = status in [
            "main_facility_online",
            "main_facility_and_supporting_above_online",
        ]
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
            self.show_toast_notification(title, message, toast_type, 3000, status)

    def on_force_check_completed(
        self, status, controller_info, supporting_info, supporting_below_controllers
    ):
        """Handle force check completion - always show notification"""
        # Update internal state
        self.current_status = status
        self.main_facility_online = status in [
            "main_facility_online",
            "main_facility_and_supporting_above_online",
        ]
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
        supporting_below_info = self.format_supporting_below_controllers_info(
            supporting_below_controllers
        )

        if status == "main_facility_and_supporting_above_online":
            main_facility_info = self.format_multiple_controllers_info(
                controller_info, "Main Facility: "
            )
            support_info = self.format_multiple_controllers_info(
                supporting_info, "Supporting Above: "
            )
            message = f"{main_facility_info}\n{support_info}{supporting_below_info}"
            self.show_toast_notification(
                f"{self.display_name} Status", message, "success", 3000, status
            )
        elif status == "main_facility_online":
            main_facility_info = self.format_multiple_controllers_info(controller_info)
            message = f"{main_facility_info} is online{supporting_below_info}"
            self.show_toast_notification(
                f"{self.display_name} Status", message, "success", 3000, status
            )
        elif status == "supporting_above_online":
            support_info = self.format_multiple_controllers_info(supporting_info)
            message = f"Main facility offline, but {support_info} is online{supporting_below_info}"
            self.show_toast_notification(
                f"{self.display_name} Status", message, "warning", 3000, status
            )
        else:  # all_offline
            message = f"No controllers found{supporting_below_info}"
            self.show_toast_notification(
                f"{self.display_name} Status", message, "info", 3000, status
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
            logging.info("Stopped VATSIM monitoring")

    def force_check(self):
        """Force an immediate check"""
        if self.monitoring:
            # Signal the worker thread to perform an immediate check
            logging.info("Requesting immediate check...")
            self.worker.force_check_requested.emit()
        else:
            self.show_toast_notification(
                "Monitor Not Running",
                "Start monitoring first",
                "warning",
                2000,
                "error",
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
                self.current_status,
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

        # Process any remaining events to ensure cleanup
        self.processEvents()

        # Quit the application gracefully
        self.quit()
