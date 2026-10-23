"""Glicko rating model
"""
from dataclasses import dataclass


@dataclass
class GlickoRating:
    mu: float
    phi: float
    sigma: float
