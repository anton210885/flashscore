"""strategy_builder — automatische Strategie-Suche für Flashscore (Lernzeitraum → Prüfzeitraum)."""

from .search_space import SEARCH_SPACE, sample_combination
from .searcher import pretty_print, run_search

__all__ = ["run_search", "pretty_print", "SEARCH_SPACE", "sample_combination"]
