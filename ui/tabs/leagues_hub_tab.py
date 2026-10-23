"""Ligen-Hub: Meisterschaften (26/27), Liga 128 (Kalender 2026), European."""
import tkinter as tk
from tkinter import ttk

from ui.tabs.league_tab import LeagueTab
from ui.tabs.league_128_tab import League128Tab
from ui.tabs.european_competition_tab import EuropeanCompetitionTab


class LeaguesHubTab(tk.Frame):
    """Ein Tab „Ligen“ mit Untertabs für die drei Liga-Gruppen."""

    def __init__(self, parent, services=None):
        super().__init__(parent)
        self.services = services or {}

        hint = ttk.Label(
            self,
            text=(
                "Meisterschaften = Saison 26/27 (Start 2026, Ende 2027)  ·  "
                "Liga 128 = Kalenderjahr 2026  ·  "
                "European = UEFA-Wettbewerbe"
            ),
            foreground="#64748b",
            wraplength=900,
            justify=tk.LEFT,
        )
        hint.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.sub = ttk.Notebook(self)
        self.sub.pack(fill=tk.BOTH, expand=True)

        self.meisterschaften_tab = LeagueTab(self.sub, services=self.services)
        self.sub.add(self.meisterschaften_tab, text="Meisterschaften (26/27)")

        self.liga128_tab = League128Tab(self.sub, services=self.services)
        self.sub.add(self.liga128_tab, text="Liga 128 (Kalender 2026)")

        self.european_tab = EuropeanCompetitionTab(self.sub, services=self.services)
        self.sub.add(self.european_tab, text="European 🇪🇺")

    # Kompatibilität für DatabaseTab / andere Referenzen
    @property
    def league_tab(self):
        return self.meisterschaften_tab

    @property
    def league_128_tab(self):
        return self.liga128_tab
