#!/usr/bin/env python3
"""
GUI Components module for VATSIM Tower Monitor
Contains dialog classes and custom toast notification system.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QTextEdit,
    QApplication,
    QCheckBox,
    QGroupBox,
    QFormLayout,
)
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QRect,
    QEasingCurve,
)
from PyQt6.QtGui import QFont
from shared.utils import translate_controller_rating, calculate_time_online


class CustomToast(QDialog):
    """Custom toast notification widget with multiline support"""

    def __init__(
        self,
        title,
        message,
        toast_type="success",
        duration=3000,
        bg_color=None,
        parent=None,
    ):
        super().__init__(parent)
        self.duration = duration
        self.toast_type = toast_type
        self.bg_color = bg_color

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
        title_font = QFont("Calibri")
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white;")
        layout.addWidget(title_label)

        # Message label (supports multiline)
        message_label = QLabel(message)
        message_font = QFont("Calibri")
        message_font.setPointSize(10)
        message_label.setFont(message_font)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: white;")
        layout.addWidget(message_label)

        self.setLayout(layout)

        # Set background color - use provided color or fallback to type-based colors
        if self.bg_color:
            bg_color = self.bg_color
        elif self.toast_type == "success":
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
Rating: {translate_controller_rating(supporting_below.get('rating', 'Unknown'))}
Time Online: {calculate_time_online(supporting_below.get('logon_time', 'Unknown'))}
Server: {supporting_below.get('server', 'Unknown')}"""
            return supporting_below_details

        supporting_below_details = format_supporting_below_controllers_details(
            supporting_below_controllers
        )

        def format_controller_details(controllers, title):
            """Helper function to format controller details"""
            if not controllers:
                return f"{title}: OFFLINE\n"

            if isinstance(controllers, dict):  # Handle legacy single controller format
                controllers = [controllers]

            details = f"{title}:\n"
            for i, controller in enumerate(controllers, 1):
                if len(controllers) > 1:
                    details += f"\nController {i}:\n"
                details += f"""Callsign: {controller.get('callsign', 'Unknown')}
Name: {controller.get('name', 'Unknown')}
Frequency: {controller.get('frequency', 'Unknown')}
Rating: {translate_controller_rating(controller.get('rating', 'Unknown'))}
Time Online: {calculate_time_online(controller.get('logon_time', 'Unknown'))}
Server: {controller.get('server', 'Unknown')}
"""
            return details

        if (
            status == "main_facility_and_supporting_above_online"
            and controller_info
            and supporting_info
        ):
            main_details = format_controller_details(
                controller_info, "Main Facility Controller Information"
            )
            support_details = format_controller_details(
                supporting_info, "Supporting Above Facility Information"
            )
            details = f"{main_details}\n{support_details}{supporting_below_details}"

        elif status == "main_facility_online" and controller_info:
            main_details = format_controller_details(
                controller_info, "Main Facility Controller Information"
            )
            details = f"{main_details}{supporting_below_details}"

        elif status == "supporting_above_online" and supporting_info:
            main_details = format_controller_details([], "Main Facility Controller")
            support_details = format_controller_details(
                supporting_info, "Supporting Above Facility Online"
            )
            details = f"{main_details}\n{support_details}{supporting_below_details}"
        else:
            details = f"No main facility or supporting above controllers currently online.{supporting_below_details}"

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

    def __init__(self, current_interval, config, pushover_service=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VATSIM Monitor Settings")
        self.setFixedSize(450, 400)
        self.config = config
        self.pushover_service = pushover_service

        layout = QVBoxLayout()

        # Monitoring settings group
        monitoring_group = QGroupBox("Monitoring Settings")
        monitoring_layout = QFormLayout()
        
        self.interval_input = QLineEdit(str(current_interval))
        monitoring_layout.addRow("Check Interval (seconds):", self.interval_input)
        
        monitoring_group.setLayout(monitoring_layout)
        layout.addWidget(monitoring_group)

        # Pushover settings group
        pushover_group = QGroupBox("Pushover Notifications")
        pushover_layout = QFormLayout()
        
        # Get current pushover config
        pushover_config = self.config.get("pushover", {})
        
        # Enable/disable checkbox
        self.pushover_enabled = QCheckBox()
        self.pushover_enabled.setChecked(pushover_config.get("enabled", False))
        pushover_layout.addRow("Enable Pushover:", self.pushover_enabled)
        
        # API token input
        self.api_token_input = QLineEdit(pushover_config.get("api_token", ""))
        self.api_token_input.setPlaceholderText("Enter your Pushover API token")
        self.api_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        pushover_layout.addRow("API Token:", self.api_token_input)
        
        # User key input
        self.user_key_input = QLineEdit(pushover_config.get("user_key", ""))
        self.user_key_input.setPlaceholderText("Enter your Pushover user key")
        pushover_layout.addRow("User Key:", self.user_key_input)
        
        # Test button
        self.test_pushover_button = QPushButton("Test Pushover")
        self.test_pushover_button.clicked.connect(self.test_pushover)
        pushover_layout.addRow("", self.test_pushover_button)
        
        pushover_group.setLayout(pushover_layout)
        layout.addWidget(pushover_group)

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
        self.pushover_settings_changed = False

    def test_pushover(self):
        """Test Pushover configuration"""
        try:
            api_token = self.api_token_input.text().strip()
            user_key = self.user_key_input.text().strip()
            
            if not api_token:
                QMessageBox.warning(self, "Missing API Token", "Please enter your Pushover API token first.")
                return
                
            if not user_key:
                QMessageBox.warning(self, "Missing User Key", "Please enter your Pushover user key first.")
                return
                
            # Create temporary pushover service for testing
            from shared.pushover_service import PushoverService
            test_service = PushoverService(api_token, user_key)
            
            # First validate the user key
            validation_result = test_service.validate_user_key()
            if not validation_result["success"]:
                QMessageBox.warning(
                    self,
                    "Invalid User Key",
                    f"User key validation failed: {validation_result['error']}"
                )
                return
            
            # Send test notification
            result = test_service.send_test_notification()
            
            if result["success"]:
                QMessageBox.information(
                    self,
                    "Test Successful",
                    "Test notification sent successfully! Check your device."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Test Failed",
                    f"Failed to send test notification: {result['error']}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Test Error",
                f"An error occurred during testing: {str(e)}"
            )

    def save_settings(self):
        """Save settings and close dialog"""
        try:
            # Validate interval
            interval = int(self.interval_input.text())
            if interval < 30:
                QMessageBox.warning(
                    self, "Invalid Input", "Check interval must be at least 30 seconds."
                )
                return
                
            # Check if pushover settings changed
            pushover_config = self.config.get("pushover", {})
            old_enabled = pushover_config.get("enabled", False)
            old_api_token = pushover_config.get("api_token", "")
            old_user_key = pushover_config.get("user_key", "")
            
            new_enabled = self.pushover_enabled.isChecked()
            new_api_token = self.api_token_input.text().strip()
            new_user_key = self.user_key_input.text().strip()
            
            if old_enabled != new_enabled or old_api_token != new_api_token or old_user_key != new_user_key:
                self.pushover_settings_changed = True
                
            self.new_interval = interval
            self.new_pushover_enabled = new_enabled
            self.new_api_token = new_api_token
            self.new_user_key = new_user_key
            
            self.accept()
            
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number for check interval.")