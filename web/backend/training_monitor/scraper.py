#!/usr/bin/env python3
"""
OAK ARTCC Training Session Scraper
"""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib
import re

# Configure logger
logger = logging.getLogger(__name__)

class TrainingSessionScraper:
    """Scraper for OAK ARTCC training sessions"""
    
    def __init__(self):
        self.base_url = "https://oakartcc.org/training/rpo-tools"
        self.session = requests.Session()
        
        # Set up headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'identity',  # Disable compression to avoid issues
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def validate_session_key(self, php_session_key: str) -> Dict[str, Any]:
        """
        Validate PHP session key by attempting to access the training page
        
        Args:
            php_session_key: PHP session ID for oakartcc.org
            
        Returns:
            Dict with validation result
        """
        try:
            logger.debug(f"Validating PHP session key: {php_session_key[:8]}...")
            
            # Set the PHP session cookie
            self.session.cookies.set('PHPSESSID', php_session_key, domain='oakartcc.org')
            
            # Attempt to fetch the training page
            response = self.session.get(self.base_url, timeout=30)
            
            if response.status_code == 200:
                # Check if we got the actual training page content
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for the training sessions table
                table = soup.find('table', class_='table table-striped')
                
                if table:
                    logger.info(f"PHP session key validation successful")
                    return {
                        'valid': True,
                        'message': 'Session key is valid and training page is accessible',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                else:
                    # Page loaded but doesn't contain expected content
                    logger.warning("PHP session key may be expired - no training table found")
                    return {
                        'valid': False,
                        'message': 'Session key may be expired - training content not accessible',
                        'timestamp': datetime.utcnow().isoformat()
                    }
            
            elif response.status_code == 401:
                logger.warning("PHP session key is unauthorized")
                return {
                    'valid': False,
                    'message': 'Session key is unauthorized or expired',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            elif response.status_code == 403:
                logger.warning("PHP session key is forbidden")
                return {
                    'valid': False,
                    'message': 'Access forbidden with current session key',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            else:
                logger.error(f"Unexpected status code during validation: {response.status_code}")
                return {
                    'valid': False,
                    'message': f'Unexpected response: HTTP {response.status_code}',
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        except requests.exceptions.Timeout:
            logger.error("Timeout during session key validation")
            return {
                'valid': False,
                'message': 'Request timeout - please try again later',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during validation: {e}")
            return {
                'valid': False,
                'message': f'Network error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}", exc_info=True)
            return {
                'valid': False,
                'message': f'Unexpected error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def scrape_training_sessions(self, php_session_key: str) -> Dict[str, Any]:
        """
        Scrape training sessions from OAK ARTCC website
        
        Args:
            php_session_key: PHP session ID for oakartcc.org
            
        Returns:
            Dict containing sessions data and metadata
        """
        try:
            logger.debug(f"Scraping training sessions with session key: {php_session_key[:8]}...")
            
            # Set the PHP session cookie
            self.session.cookies.set('PHPSESSID', php_session_key, domain='oakartcc.org')
            
            # Fetch the training page
            response = self.session.get(self.base_url, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch training page: HTTP {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code} - Failed to access training page',
                    'sessions': [],
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the training sessions table
            table = soup.find('table', class_='table table-striped')
            
            if not table:
                logger.warning("No training sessions table found - session key may be expired")
                return {
                    'success': False,
                    'error': 'Training sessions table not found - session key may be expired',
                    'sessions': [],
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Parse table rows
            sessions = []
            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody and hasattr(tbody, 'find_all') else []
            
            for row in rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        session_data = self._parse_session_row(cells)
                        if session_data:
                            sessions.append(session_data)
                except Exception as e:
                    logger.error(f"Error parsing table row: {e}", exc_info=True)
                    continue
            
            logger.info(f"Successfully scraped {len(sessions)} training sessions")
            
            return {
                'success': True,
                'sessions': sessions,
                'total_sessions': len(sessions),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except requests.exceptions.Timeout:
            logger.error("Timeout during training session scraping")
            return {
                'success': False,
                'error': 'Request timeout - please try again later',
                'sessions': [],
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during scraping: {e}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}',
                'sessions': [],
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'sessions': [],
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _parse_session_row(self, cells) -> Optional[Dict[str, Any]]:
        """
        Parse a training session table row
        
        Args:
            cells: List of BeautifulSoup TD elements
            
        Returns:
            Dict with session data or None if parsing fails
        """
        try:
            # Extract student info (name and rating badge)
            student_cell = cells[0]
            student_name = student_cell.get_text().strip()
            
            # Extract student rating from badge
            student_rating = None
            rating_badge = student_cell.find('span', class_='badge controller-rating')
            if rating_badge:
                student_rating = rating_badge.get_text().strip()
                # Clean student name by removing the rating badge text
                student_name = re.sub(r'\s+' + re.escape(student_rating) + r'\s*$', '', student_name).strip()
            
            # Extract instructor name
            instructor_name = cells[1].get_text().strip()
            
            # Extract module info
            module_cell = cells[2]
            module_link = module_cell.find('a')
            
            if module_link:
                module_name = module_link.get_text().strip()
                module_url = module_link.get('href', '')
            else:
                module_name = module_cell.get_text().strip()
                module_url = ''
            
            # Extract date and time
            session_date = cells[3].get_text().strip()
            session_time = cells[4].get_text().strip()
            
            # Generate a hash for deduplication
            session_hash = self._generate_session_hash(
                student_name, instructor_name, module_name, session_date, session_time
            )
            
            # Extract rating pattern from module name
            rating_pattern = self._extract_rating_pattern(module_name)
            
            session_data = {
                'student_name': student_name,
                'student_rating': student_rating,
                'instructor_name': instructor_name,
                'module_name': module_name,
                'module_url': module_url,
                'session_date': session_date,
                'session_time': session_time,
                'rating_pattern': rating_pattern,
                'session_hash': session_hash
            }
            
            logger.debug(f"Parsed session: {student_name} -> {rating_pattern}")
            return session_data
        
        except Exception as e:
            logger.error(f"Error parsing session row: {e}", exc_info=True)
            return None
    
    def _extract_rating_pattern(self, module_name: str) -> Optional[str]:
        """
        Extract rating pattern from module name (e.g., 'S1-OAK', 'S2-OAK')
        
        Args:
            module_name: Full module name
            
        Returns:
            Rating pattern or None if not found
        """
        # Look for patterns like S1-OAK, S2-OAK, C1-SFO, etc.
        pattern_match = re.search(r'([SC]\d+-[A-Z]{3})', module_name)
        
        if pattern_match:
            return pattern_match.group(1)
        
        return None
    
    def _generate_session_hash(self, student_name: str, instructor_name: str, 
                             module_name: str, session_date: str, session_time: str) -> str:
        """
        Generate a unique hash for a training session for deduplication
        
        Args:
            student_name: Student name
            instructor_name: Instructor name
            module_name: Module name
            session_date: Session date
            session_time: Session time
            
        Returns:
            SHA-256 hash string
        """
        # Combine all session details into a string
        session_string = f"{student_name}|{instructor_name}|{module_name}|{session_date}|{session_time}"
        
        # Generate SHA-256 hash
        return hashlib.sha256(session_string.encode('utf-8')).hexdigest()
    
    def filter_sessions_by_ratings(self, sessions: List[Dict[str, Any]], 
                                 monitored_ratings: List[str]) -> List[Dict[str, Any]]:
        """
        Filter training sessions by monitored rating patterns
        
        Args:
            sessions: List of training sessions
            monitored_ratings: List of rating patterns to monitor (e.g., ['S1-OAK', 'S2-OAK'])
            
        Returns:
            Filtered list of sessions
        """
        if not monitored_ratings:
            logger.debug("No monitored ratings configured, returning empty list")
            return []
        
        filtered_sessions = []
        
        for session in sessions:
            rating_pattern = session.get('rating_pattern')
            
            if rating_pattern and rating_pattern in monitored_ratings:
                filtered_sessions.append(session)
                logger.debug(f"Session matches monitored rating: {rating_pattern} for {session['student_name']}")
        
        logger.info(f"Filtered {len(filtered_sessions)} sessions from {len(sessions)} total sessions")
        return filtered_sessions
    
    def detect_new_sessions(self, current_sessions: List[Dict[str, Any]], 
                          cached_sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect new sessions by comparing current with cached sessions
        
        Args:
            current_sessions: Current session list
            cached_sessions: Previously cached session list
            
        Returns:
            List of new sessions
        """
        if not cached_sessions:
            logger.info("No cached sessions found, all current sessions are considered new")
            return current_sessions
        
        # Create set of cached session hashes
        cached_hashes = {session.get('session_hash') for session in cached_sessions}
        
        # Find new sessions
        new_sessions = []
        for session in current_sessions:
            session_hash = session.get('session_hash')
            if session_hash and session_hash not in cached_hashes:
                new_sessions.append(session)
        
        logger.info(f"Detected {len(new_sessions)} new sessions")
        return new_sessions