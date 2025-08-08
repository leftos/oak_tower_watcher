#!/usr/bin/env python3
"""
Forms for user authentication and settings management
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, FieldList, FormField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from .models import User
import re

class LoginForm(FlaskForm):
    """User login form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """User registration form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')
    
    def validate_email(self, email):
        """Check if email is already registered or banned"""
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            if user.is_banned:
                raise ValidationError('This email address is banned and cannot be used to register.')
            else:
                raise ValidationError('Please use a different email address.')

class UserSettingsForm(FlaskForm):
    """User settings form for service configuration"""
    pushover_api_token = StringField('Pushover API Token', validators=[
        Length(max=255, message='API Token too long')
    ])
    pushover_user_key = StringField('Pushover User Key', validators=[
        Length(max=255, message='User Key too long')
    ])
    notifications_enabled = BooleanField('Enable Notifications', default=True)
    submit = SubmitField('Save Settings')

class GeneralSettingsForm(FlaskForm):
    """General user settings form for global configuration"""
    pushover_api_token = StringField('Pushover API Token', validators=[
        Length(max=255, message='API Token too long')
    ])
    pushover_user_key = StringField('Pushover User Key', validators=[
        Length(max=255, message='User Key too long')
    ])
    submit = SubmitField('Save Settings')

class PasswordResetRequestForm(FlaskForm):
    """Password reset request form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Password Reset Email')

class PasswordResetForm(FlaskForm):
    """Password reset form with new password"""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    password2 = PasswordField('Repeat New Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')


# Facility-specific forms have been moved to facility_monitor/forms.py