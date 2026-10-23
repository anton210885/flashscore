"""Reload xG data automatically (no confirmation)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import and run the fixed script with auto flag
from scripts.reload_xg_fixed import reload_xg_fixed
import sys as sys_module

# Set auto flag
sys_module.argv = ['reload_xg_fixed.py', '--auto']
reload_xg_fixed()























