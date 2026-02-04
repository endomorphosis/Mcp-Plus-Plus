"""
MCP++ Testing Framework
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))
