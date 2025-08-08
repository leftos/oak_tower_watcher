#!/usr/bin/env python3
"""
Training Session Monitor Forms
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, SelectMultipleField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import CheckboxInput, ListWidget
from .models import get_available_rating_patterns

class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class TrainingSessionSettingsForm(FlaskForm):
    """Form for training session monitoring settings"""
    
    # Notification settings
    notifications_enabled = BooleanField(
        'Enable Notifications',
        description='Receive push notifications when new training sessions are scheduled',
        default=True
    )
    
    # PHP Session key
    php_session_key = StringField(
        'OAK ARTCC PHP Session Key',
        description='Your PHP session ID from oakartcc.org (found in browser cookies as PHPSESSID)',
        validators=[Optional(), Length(min=10, max=100)],
        render_kw={
            'placeholder': 'e.g., 94e3jaq64t8mfrtv246krkm5nb',
            'class': 'form-control'
        }
    )
    
    # Monitored ratings
    monitored_ratings = MultiCheckboxField(
        'Monitored Ratings',
        description='Select which rating types you want to monitor for new training sessions',
        choices=[],  # Will be populated dynamically
        validators=[Optional()]
    )
    
    # Submit button
    submit = SubmitField('Save Settings', render_kw={'class': 'btn btn-primary'})
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate rating choices dynamically
        available_ratings = get_available_rating_patterns()
        self.monitored_ratings.choices = [(rating, rating) for rating in available_ratings]

class TestSessionKeyForm(FlaskForm):
    """Form for testing PHP session key"""
    
    php_session_key = StringField(
        'PHP Session Key to Test',
        description='Enter the PHP session key to validate',
        validators=[DataRequired(), Length(min=10, max=100)],
        render_kw={
            'placeholder': 'e.g., 94e3jaq64t8mfrtv246krkm5nb',
            'class': 'form-control'
        }
    )
    
    test_submit = SubmitField('Test Session Key', render_kw={'class': 'btn btn-info'})