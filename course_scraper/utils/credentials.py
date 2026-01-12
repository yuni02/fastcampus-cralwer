"""
Credentials loading utilities for course_scraper
"""
import os
from typing import Dict, Any, Optional, Tuple

# Project root path (course_scraper directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, 'credentials.py')

# Cached credentials
_credentials_cache: Optional[Dict[str, Any]] = None


def _load_credentials() -> Dict[str, Any]:
    """Load credentials from credentials.py file"""
    global _credentials_cache

    if _credentials_cache is not None:
        return _credentials_cache

    # Default values
    credentials = {
        'MYSQL_HOST': 'localhost',
        'MYSQL_PORT': 3306,
        'MYSQL_USER': 'root',
        'MYSQL_PASSWORD': '',
        'MYSQL_DATABASE': 'crawler',
        'KAKAO_EMAIL': None,
        'KAKAO_PASSWORD': None,
    }

    if os.path.exists(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
            exec_globals = {}
            exec(f.read(), exec_globals)

            for key in credentials.keys():
                if key in exec_globals:
                    credentials[key] = exec_globals[key]
    else:
        raise FileNotFoundError(
            f"credentials.py not found at {CREDENTIALS_PATH}. "
            "Please create it from credentials_example.py"
        )

    _credentials_cache = credentials
    return credentials


def get_credentials() -> Dict[str, Any]:
    """Get all credentials as a dictionary"""
    return _load_credentials()


def get_db_config() -> Dict[str, Any]:
    """Get database configuration"""
    creds = _load_credentials()
    return {
        'host': creds['MYSQL_HOST'],
        'port': creds['MYSQL_PORT'],
        'user': creds['MYSQL_USER'],
        'password': creds['MYSQL_PASSWORD'],
        'database': creds['MYSQL_DATABASE'],
    }


def get_kakao_credentials() -> Tuple[str, str]:
    """
    Get Kakao credentials

    Returns:
        Tuple of (email, password)

    Raises:
        ValueError if credentials are not set
    """
    creds = _load_credentials()

    email = creds.get('KAKAO_EMAIL')
    password = creds.get('KAKAO_PASSWORD')

    if not email or not password:
        raise ValueError("KAKAO_EMAIL or KAKAO_PASSWORD not set in credentials.py")

    return email, password


def clear_cache():
    """Clear credentials cache (useful for testing)"""
    global _credentials_cache
    _credentials_cache = None
