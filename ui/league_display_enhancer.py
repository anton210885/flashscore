"""Anzeige-Hilfen für den League-Tab: Tooltips, Sparklines, Filter, Watchlist."""
from __future__ import annotations

import json
import os
import tkinter as tk
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Kompakte Header + volle Tooltip-Texte
COMPACT_HEADINGS: Dict[str, Tuple[str, str]] = {
    "Country": ("Land", "Land"),
    "ID": ("ID", "Liga-ID"),
    "Name": ("Liga", "Liganame"),
    "Heute": ("Heute", "Noch ausstehende Spiele heute (ohne bereits beendete)"),
    "CurrentSeason": ("Saison", "Aktuelle Saison der Liga"),
    "Games_2026": ("Spiele", "Anzahl Spiele Saison 2026 (26/27)"),
    "Alarm": ("Alarm", "Tiefpunkt-Signal (Regression zur Historie)"),
    "Streak2.5_2026": ("Streak", "Aktuelle Under-2.5-Streak 2026"),
    "Streak3.5_2026": ("Streak", "Aktuelle Under-3.5-Streak 2026"),
    "Streak4.5_2026": ("Streak", "Aktuelle Under-4.5-Streak 2026"),
    "Last10_2.5_2026": ("L10", "Over 2.5 in den letzten 10 Spielen"),
    "Last20_2.5_2026": ("L20", "Over 2.5 in den letzten 20 Spielen"),
    "Last10_3.5_2026": ("L10", "Over 3.5 in den letzten 10 Spielen"),
    "Last20_3.5_2026": ("L20", "Over 3.5 in den letzten 20 Spielen"),
    "Last10_4.5_2026": ("L10", "Over 4.5 in den letzten 10 Spielen"),
    "Last20_4.5_2026": ("L20", "Over 4.5 in den letzten 20 Spielen"),
    "Avg2.5_2022_2025": ("Avg", "Ø Over 2.5 (2022–2025)"),
    "Avg3.5_2022_2025": ("Avg", "Ø Over 3.5 (2022–2025)"),
    "Avg4.5_2022_2025": ("Avg", "Ø Over 4.5 (2022–2025)"),
    "Diff2.5_2026_Avg": ("Diff", "2026 minus historischer Avg"),
    "Diff3.5_2026_Avg": ("Diff", "2026 minus historischer Avg"),
    "Diff4.5_2026_Avg": ("Diff", "2026 minus historischer Avg"),
    "Diff2.5_Last10_Avg": ("ΔL10", "Last10 minus Avg"),
    "Diff2.5_Last20_Avg": ("ΔL20", "Last20 minus Avg"),
    "Diff3.5_Last10_Avg": ("ΔL10", "Last10 minus Avg"),
    "Diff3.5_Last20_Avg": ("ΔL20", "Last20 minus Avg"),
    "Diff4.5_Last10_Avg": ("ΔL10", "Last10 minus Avg"),
    "Diff4.5_Last20_Avg": ("ΔL20", "Last20 minus Avg"),
    "Trend2.5": ("Trend", "Last10 → Saison → Avg (Sparkline)"),
    "Trend3.5": ("Trend", "Last10 → Saison → Avg (Sparkline)"),
    "Trend4.5": ("Trend", "Last10 → Saison → Avg (Sparkline)"),
    "MedianStreak2.5": ("MedStr", "Median-Streak 2022–2025"),
    "MedianStreak3.5": ("MedStr", "Median-Streak 2022–2025"),
    "MedianStreak4.5": ("MedStr", "Median-Streak 2022–2025"),
    "MaxOfMax2.5": ("MoM", "Max of Max Streak 2.5"),
    "MaxOfMax3.5": ("MoM", "Max of Max Streak 3.5"),
    "MaxOfMax4.5": ("MoM", "Max of Max Streak 4.5"),
}

# Spalten-Sets: welche Spalten in welchem Modus sichtbar (Rest width=0)
VIEW_VISIBLE: Dict[str, Dict[str, Sequence[str]]] = {
    "kompakt": {
        "25": (
            "Country", "ID", "Name", "Heute", "Games_2026", "Alarm", "Streak2.5_2026",
            "Over2.5_2026", "Last10_2.5_2026", "Avg2.5_2022_2025", "Diff2.5_2026_Avg",
            "Trend2.5", "MaxOfMax2.5",
        ),
        "35": (
            "Country", "ID", "Name", "Heute", "Games_2026", "Alarm", "Streak3.5_2026",
            "Over3.5_2026", "Last10_3.5_2026", "Avg3.5_2022_2025", "Diff3.5_2026_Avg",
            "Trend3.5", "MaxOfMax3.5",
        ),
        "45": (
            "Country", "ID", "Name", "Heute", "Games_2026", "Alarm", "Streak4.5_2026",
            "Over4.5_2026", "Last10_4.5_2026", "Avg4.5_2022_2025", "Diff4.5_2026_Avg",
            "Trend4.5", "MaxOfMax4.5",
        ),
    },
    "vergleich": {
        "25": (
            "Country", "ID", "Name", "Heute", "Games_2026", "Alarm", "Streak2.5_2026",
            "Over2.5_2026", "Over2.5_2025", "Over2.5_2024", "Over2.5_2023", "Over2.5_2022",
            "Last10_2.5_2026", "Last20_2.5_2026", "Avg2.5_2022_2025",
            "Diff2.5_2026_Avg", "Diff2.5_Last10_Avg", "Trend2.5", "MaxOfMax2.5",
        ),
        "35": (
            "Country", "ID", "Name", "Heute", "Games_2026", "Alarm", "Streak3.5_2026",
            "Over3.5_2026", "Over3.5_2025", "Over3.5_2024", "Over3.5_2023", "Over3.5_2022",
            "Last10_3.5_2026", "Last20_3.5_2026", "Avg3.5_2022_2025",
            "Diff3.5_2026_Avg", "Diff3.5_Last10_Avg", "Trend3.5", "MaxOfMax3.5",
        ),
        "45": (
            "Country", "ID", "Name", "Heute", "Games_2026", "Alarm", "Streak4.5_2026",
            "Over4.5_2026", "Over4.5_2025", "Over4.5_2024", "Over4.5_2023", "Over4.5_2022",
            "Last10_4.5_2026", "Last20_4.5_2026", "Avg4.5_2022_2025",
            "Diff4.5_2026_Avg", "Diff4.5_Last10_Avg", "Trend4.5", "MaxOfMax4.5",
        ),
    },
    # voll = alle Spalten (None → show all)
    "voll": {"25": (), "35": (), "45": ()},
}

# Spalten die links „fixiert“ wirken sollen (immer zuerst, kompakt sichtbar)
FROZEN_COLS = ("Country", "ID", "Name", "Heute")

STREAK_COL_HINTS = {
    "Streak2.5_2026": "25",
    "Streak3.5_2026": "35",
    "Streak4.5_2026": "45",
    "Streak2.5": "25",
    "Streak3.5": "35",
    "Streak4.5": "45",
}


WATCHLIST_PATH = os.path.join("data", "league_watchlist.json")

# Gelb → Rot für Alarm-Glocke (Tiefpunkt: aktuelle Saison unter Historie)
ALARM_HEAT_COLORS: Tuple[str, ...] = (
    "#fef9c3",
    "#fef08a",
    "#fde047",
    "#fdba74",
    "#f87171",
    "#dc2626",
)


def streak_magnitude(value: Any) -> int:
    """Under-Streak: negative Zahl → Länge als positive Ganzzahl."""
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return 0
    if v < 0:
        return abs(v)
    return v if v > 0 else 0


def streak_alert_level(current: Any, median: Any, maximum: Any) -> Optional[str]:
    """Gelb wenn Streak > Median, rot wenn Streak > Maximum."""
    cur = streak_magnitude(current)
    if cur <= 0:
        return None
    try:
        med = float(median or 0)
    except (TypeError, ValueError):
        med = 0.0
    try:
        mx = float(maximum or 0)
    except (TypeError, ValueError):
        mx = 0.0
    if mx > 0 and cur > mx:
        return "red"
    if med > 0 and cur > med:
        return "yellow"
    return None


def build_streak_special_signal(current: Any, median: Any, maximum: Any) -> str:
    level = streak_alert_level(current, median, maximum)
    if level == "red":
        return "🔴 > Max"
    if level == "yellow":
        return "🟡 > Med"
    return ""


def format_streak_cell(current: Any, median: Any, maximum: Any) -> str:
    try:
        base = str(int(float(current)))
    except (TypeError, ValueError):
        base = str(current or 0)
    level = streak_alert_level(current, median, maximum)
    if level == "red":
        return f"{base} 🔴"
    if level == "yellow":
        return f"{base} 🟡"
    return base


def parse_percent_value(val: Any) -> Optional[float]:
    if val is None or val in ("", "N/A", "Error", "–", "-"):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    for ch in ("▲", "▼", "·", " "):
        s = s.replace(ch, "")
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


def alarm_season_deviation(league: Dict[str, Any], metric_prefix: str, history_years: Sequence[str]) -> Optional[float]:
    """Positiv = aktuelle Saison unter historischem Ø (Tiefpunkt)."""
    current = parse_percent_value(league.get(f"{metric_prefix}_2026", None))
    if current is None:
        return None
    hist = []
    for year in history_years:
        p = parse_percent_value(league.get(f"{metric_prefix}_{year}", None))
        if p is not None:
            hist.append(p)
    if not hist:
        return None
    return (sum(hist) / len(hist)) - current


def alarm_heat_index(deviation: Optional[float], max_deviation: float = 25.0) -> int:
    if deviation is None or deviation <= 0:
        return 0
    ratio = min(1.0, float(deviation) / float(max_deviation))
    return max(1, min(5, int(round(ratio * 5))))


def alarm_heat_color(index: int) -> str:
    if index <= 0:
        return ""
    return ALARM_HEAT_COLORS[min(index, len(ALARM_HEAT_COLORS) - 1)]


def format_alarm_bell(base_alarm: str, deviation: Optional[float], max_deviation: float = 25.0) -> str:
    if not base_alarm:
        return ""
    idx = alarm_heat_index(deviation, max_deviation)
    markers = ("", "🟡", "🟨", "🟧", "🟠", "🔴")
    marker = markers[idx] if idx else "🟡"
    return f"{marker}{base_alarm}"


def first_numeric(league: Dict[str, Any], keys: Sequence[str]) -> float:
    for key in keys:
        value = league.get(key)
        if isinstance(value, (int, float)) and value != "Error":
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return 0.0


def format_diff(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "·")
    return f"{arrow}{val:+.1f}%"


def sparkline_bars(values: Sequence[Optional[float]], width: int = 7) -> str:
    """Unicode-Sparkline aus Prozentwerten."""
    nums = [v for v in values if v is not None]
    if not nums:
        return "—"
    lo, hi = min(nums), max(nums)
    blocks = "▁▂▃▄▅▆▇"
    out = []
    for v in values:
        if v is None:
            out.append("·")
            continue
        if hi <= lo:
            idx = 3
        else:
            idx = int(round((v - lo) / (hi - lo) * (len(blocks) - 1)))
            idx = max(0, min(len(blocks) - 1, idx))
        out.append(blocks[idx])
    return "".join(out)


def build_trend_cell(last10: Any, season: Any, avg: Any) -> str:
    a = parse_percent_value(last10)
    b = parse_percent_value(season)
    c = parse_percent_value(avg)
    bars = sparkline_bars([a, b, c])
    parts = []
    for v in (a, b, c):
        parts.append(f"{v:.0f}" if v is not None else "–")
    return f"{bars} {'→'.join(parts)}"


def max_streak_tooltip_text(league: Dict[str, Any], focus: str = "25") -> str:
    """Alle Max-Streak-Infos wie im Max-Streaks-Tab, für Hover."""
    name = league.get("name", "?")
    country = league.get("country", "")
    lid = league.get("id", "")
    lines = [
        f"{country} — {name} (ID {lid})",
        "─" * 36,
        "Max Streaks (wie Tab „Max Streaks“)",
        "",
    ]

    def line(label: str, key: str, fmt: str = "int") -> None:
        v = league.get(key, 0) or 0
        if fmt == "float":
            lines.append(f"  {label}: {float(v):.1f}")
        else:
            lines.append(f"  {label}: {int(v) if v else 0}")

    # Fokus zuerst
    if focus == "25":
        lines.append("Over 2.5")
        line("Max 2022", "max_streak_2022")
        line("Median 2022", "median_streak_2022", "float")
        line("Max All", "max_streak_all")
        line("Median All", "median_streak_all", "float")
        line("Max of Max", "max_of_max_25")
        for y in (2022, 2023, 2024, 2025, 2026):
            line(f"Max {y} Season", f"max_streak_{y}_25_season")
    elif focus == "35":
        lines.append("Over 3.5")
        line("Max 2022", "max_streak_2022_35")
        line("Median 2022", "median_streak_2022_35", "float")
        line("Max All", "max_streak_all_35")
        line("Median All", "median_streak_all_35", "float")
        line("Max of Max", "max_of_max_35")
        for y in (2022, 2023, 2024, 2025, 2026):
            line(f"Max {y} Season", f"max_streak_{y}_35_season")
    else:
        lines.append("Over 4.5")
        line("Max 2022", "max_streak_2022_45")
        line("Median 2022", "median_streak_2022_45", "float")
        line("Max All", "max_streak_all_45")
        line("Median All", "median_streak_all_45", "float")
        line("Max of Max", "max_of_max_45")
        for y in (2022, 2023, 2024, 2025, 2026):
            line(f"Max {y} Season", f"max_streak_{y}_45_season")

    # Kurzüberblick andere Linien
    lines.append("")
    lines.append("Kurz: 2.5 / 3.5 / 4.5")
    lines.append(
        f"  MoM: {league.get('max_of_max_25', 0) or 0} / "
        f"{league.get('max_of_max_35', 0) or 0} / "
        f"{league.get('max_of_max_45', 0) or 0}"
    )
    cur = "2026"
    lines.append(
        f"  Akt. Streak {cur}: "
        f"{league.get('streak25_2026', 0)} / "
        f"{league.get('streak35_2026', 0)} / "
        f"{league.get('streak45_2026', 0)}"
    )
    return "\n".join(lines)


def apply_compact_headings(tree) -> None:
    for col in tree["columns"]:
        short, tip = COMPACT_HEADINGS.get(col, (None, None))
        if short is None:
            # Over-Jahre kompakt
            if col.startswith("Over2.5_") or col.startswith("Over3.5_") or col.startswith("Over4.5_"):
                year = col.rsplit("_", 1)[-1]
                metric = col.split("_")[0].replace("Over", "O")
                short = f"{metric}'{year[-2:]}"
                tip = f"{col.replace('_', ' ')}"
            elif col.startswith("MaxStreak"):
                short = col.replace("MaxStreak", "Mx").replace("_Season", "").replace("_35", "·3.5").replace("_45", "·4.5")
                tip = col
            else:
                continue
        tree.heading(col, text=short)
        if not hasattr(tree, "_col_tooltips"):
            tree._col_tooltips = {}
        tree._col_tooltips[col] = tip


def apply_view_mode_widths(tree, metric_key: str, mode: str, default_widths: Dict[str, int]) -> None:
    cols = list(tree["columns"])
    visible = VIEW_VISIBLE.get(mode, {}).get(metric_key)
    if mode == "voll" or not visible:
        for col in cols:
            w = default_widths.get(col, 90)
            tree.column(col, width=w, minwidth=0)
        return
    visible_set = set(visible)
    for col in cols:
        if col in visible_set:
            w = default_widths.get(col, 90)
            # frozen-ish: keep readable
            if col in FROZEN_COLS:
                w = max(w, 70)
            tree.column(col, width=w, minwidth=20)
        else:
            tree.column(col, width=0, minwidth=0, stretch=False)


def load_watchlist() -> List[int]:
    try:
        if os.path.exists(WATCHLIST_PATH):
            with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [int(x) for x in data]
    except Exception:
        pass
    return []


def save_watchlist(ids: Sequence[int]) -> None:
    os.makedirs(os.path.dirname(WATCHLIST_PATH) or ".", exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(set(int(x) for x in ids)), f, indent=2)


class HoverTip:
    """Leichtes Tooltip-Fenster unter dem Cursor."""

    def __init__(self, widget):
        self.widget = widget
        self.tip = None
        self._after = None

    def show(self, text: str, x_root: int, y_root: int):
        self.hide()
        if not text:
            return
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x_root + 12}+{y_root + 12}")
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass
        lbl = tk.Label(
            tw,
            text=text,
            justify=tk.LEFT,
            background="#fffef5",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Consolas", 9),
            padx=8,
            pady=6,
        )
        lbl.pack()

    def hide(self):
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None
