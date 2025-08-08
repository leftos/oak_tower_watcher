#!/usr/bin/env python3
"""
Forms for facility monitoring configuration
"""

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
import re

class FacilityRegexPatternForm(FlaskForm):
    """Sub-form for individual regex patterns"""
    pattern = StringField('Regex Pattern', validators=[
        Length(max=255, message='Pattern too long')
    ])

    def validate_pattern(self, field):
        """Validate regex pattern"""
        if field.data and field.data.strip():
            try:
                re.compile(field.data, re.IGNORECASE)
            except re.error as e:
                raise ValidationError(f'Invalid regex pattern: {str(e)}')


class FacilityConfigForm(FlaskForm):
    """Form for facility regex configuration"""
    # App-specific notification setting
    notifications_enabled = BooleanField('Enable Notifications', default=True)
    
    # Facility regex patterns - stored as text areas for easier editing
    main_facility_patterns = TextAreaField('Main Facility Patterns', validators=[
        Optional()
    ])
    supporting_above_patterns = TextAreaField('Supporting Above Patterns', validators=[
        Optional()
    ])
    supporting_below_patterns = TextAreaField('Supporting Below Patterns', validators=[
        Optional()
    ])
    
    submit = SubmitField('Save Configuration')
    
    def validate_main_facility_patterns(self, field):
        """Validate main facility regex patterns"""
        self._validate_patterns_field(field, 'Main Facility')
    
    def validate_supporting_above_patterns(self, field):
        """Validate supporting above regex patterns"""
        self._validate_patterns_field(field, 'Supporting Above')
    
    def validate_supporting_below_patterns(self, field):
        """Validate supporting below regex patterns"""
        self._validate_patterns_field(field, 'Supporting Below')
    
    def _validate_patterns_field(self, field, field_name):
        """Helper method to validate regex patterns in a text area"""
        if not field.data:
            return
        
        patterns = [p.strip() for p in field.data.split('\n') if p.strip()]
        for i, pattern in enumerate(patterns):
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                raise ValidationError(f'{field_name} pattern #{i+1} is invalid: {str(e)}')
    
    def get_patterns_list(self, field_name):
        """Convert text area patterns to list"""
        field = getattr(self, field_name)
        if not field.data:
            return []
        return [p.strip() for p in field.data.split('\n') if p.strip()]
    
    def set_patterns_from_list(self, field_name, patterns_list):
        """Set text area from patterns list"""
        field = getattr(self, field_name)
        field.data = '\n'.join(patterns_list) if patterns_list else ''