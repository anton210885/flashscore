"""Database package for Flashscore game statistics"""
from .db_manager import DatabaseManager
from .connection import connect, ensure_schema

__all__ = ['DatabaseManager', 'connect', 'ensure_schema']
























