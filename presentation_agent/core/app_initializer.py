"""
Application initialization utilities.
Extracted from main.py to follow Single Responsibility Principle.
"""

import os
import logging
from pathlib import Path
from typing import Optional


class AppInitializer:
    """
    Handles application initialization: logging, environment setup, API key validation.
    """
    
    def __init__(self, output_dir: str = "presentation_agent/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self) -> None:
        """Configure logging."""
        # Clean up old log files
        for log_file in ["logger.log", "web.log", "tunnel.log", "observability.log"]:
            # Clean up old root location
            if os.path.exists(log_file):
                os.remove(log_file)
                print(f"🧹 Cleaned up {log_file}")
            # Clean up new location
            new_log_path = self.output_dir / log_file
            if new_log_path.exists():
                new_log_path.unlink()
                print(f"🧹 Cleaned up {new_log_path}")
        
        # Configure logging
        logging.basicConfig(
            filename=str(self.output_dir / "logger.log"),
            level=logging.DEBUG,
            format="%(filename)s:%(lineno)s %(levelname)s:%(message)s",
        )
        print("✅ Logging configured")
    
    def load_environment(self) -> None:
        """Load environment variables from .env file if available."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # python-dotenv not installed, skip .env loading
            pass
        except Exception as e:
            print(f"Warning: Could not load .env file: {e}")
    
    def validate_api_key(self) -> bool:
        """
        Validate that GOOGLE_API_KEY is set.
        
        Returns:
            True if API key is set, False otherwise
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("\n❌ GOOGLE_API_KEY environment variable not set")
            print("\nTo set the API key, use one of these methods:")
            print("1. Environment variable: export GOOGLE_API_KEY='your-key-here'")
            print("2. .env file: Create a .env file with: GOOGLE_API_KEY=your-key-here")
            print("   (Install python-dotenv: pip install python-dotenv)")
            print("3. Direct in code: os.environ['GOOGLE_API_KEY'] = 'your-key-here'")
            return False
        return True
    
    def initialize(self) -> bool:
        """
        Perform all initialization steps.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.setup_logging()
        self.load_environment()
        return self.validate_api_key()

