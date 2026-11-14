"""strategy_builder package — automatic strategy discovery for Flashscore."""

from .searcher import run_search, pretty_print
from .search_space import SEARCH_SPACE, sample_combination

__all__ = ["run_search", "pretty_print", "SEARCH_SPACE", "sample_combination"]
