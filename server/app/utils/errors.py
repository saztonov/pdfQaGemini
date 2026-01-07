"""Custom exceptions - re-export from shared module"""
import sys
from pathlib import Path

# Add project root to path for shared imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from shared.exceptions import AppError, ServiceError

__all__ = ["AppError", "ServiceError"]
