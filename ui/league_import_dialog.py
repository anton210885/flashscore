"""Dialog: leagues from Excel, pick rows, choose League vs Liga 128 per import."""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional

from services.league_xlsx_service import (
    parse_leagues_workbook,
    upsert_league_row,
    load_liga128_ids,
    set_league_visibility_tab,
)


DefaultRefresh = Optional[Callable[[], None]]

XLSX_SEARCH = (
    os.path.join("data", "league.xlsx"),
    "league.xlsx",
)


def pick_default_xlsx() -> Optional[str]:
    for p in XLSX_SEARCH:
        if os.path.isfile(p):
            return p
    return None


class _DestinationChooser(tk.Toplevel):
    """Returns 'league', 'liga128', 'skip', or 'abort' via self.choice."""

    def __init__(self, parent, league_id: int, name: str, country: str):
        super().__init__(parent)
        self.title(f"Liga {league_id} importieren")
        self.transient(parent)
        self.resizable(False, False)
        self.choice: Optional[str] = None

        self.var = tk.StringVar(value="league")

        msg = tk.Label(
            self,
            text=(
                f"ID {league_id}\n{name}\n{country}\n\n"
                "Wo soll diese Liga in der App sichtbar sein?"
            ),
            justify=tk.CENTER,
        )
        msg.pack(padx=14, pady=10)

        f = tk.Frame(self)
        f.pack(fill=tk.X, padx=14)
        tk.Radiobutton(
            f,
            text='Tab „League“ – normale Ligenliste',
            variable=self.var,
            value="league",
        ).pack(anchor="w")
        tk.Radiobutton(
            f,
            text='Tab „Liga 128“ – nur dort',
            variable=self.var,
            value="liga128",
        ).pack(anchor="w")

        bf = tk.Frame(self)
        bf.pack(pady=12, padx=14, fill=tk.X)

        tk.Button(bf, text="Importieren", command=self._import).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        tk.Button(bf, text="Überspringen", command=self._skip).pack(
            side=tk.LEFT, padx=6
        )
        tk.Button(bf, text="Abbrechen", command=self._abort).pack(
            side=tk.LEFT, padx=6
        )

        self.protocol("WM_DELETE_WINDOW", self._abort)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        parent.wait_window(self)

    def _import(self):
        self.choice = self.var.get()
        self.grab_release()
        self.destroy()

    def _skip(self):
        self.choice = "skip"
        self.grab_release()
        self.destroy()

    def _abort(self):
        self.choice = "abort"
        self.grab_release()
        self.destroy()


class LeagueImportDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        db_path: str = "data/flashscore.db",
        on_finished: DefaultRefresh = None,
    ):
        super().__init__(parent)
        self.title("Ligen aus Excel importieren")
        self.geometry("760x460")
        self.transient(parent)
        self.db_path = db_path
        self.on_finished = on_finished
        self.rows: List[Dict[str, Any]] = []
        self._existing_db: Dict[int, bool] = {}
        self._liga128_ids: List[int] = []
        self._path_var = tk.StringVar(value=pick_default_xlsx() or "")

        main = tk.Frame(self, padx=10, pady=8)
        main.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(main)
        top.pack(fill=tk.X)
        tk.Label(top, text="Datei:").pack(side=tk.LEFT)
        tk.Entry(top, textvariable=self._path_var, width=55).pack(
            side=tk.LEFT, padx=6, fill=tk.X, expand=True
        )
        tk.Button(top, text="Durchsuchen…", command=self._browse).pack(side=tk.LEFT)

        tk.Label(
            main,
            text=(
                "Spalten mit Überschrift z. B. league_id / id, league_name / name, "
                "optional country, country_code. Erste Checkbox-Spalte: Klick zum An-/Abwählen."
            ),
            wraplength=720,
            justify=tk.LEFT,
            fg="gray",
        ).pack(anchor="w", pady=(4, 2))

        tree_frame = tk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=6)

        cols = ("mark", "league_id", "name", "country", "code", "db_status", "visible")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("mark", text="✓")
        self.tree.heading("league_id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("country", text="Land")
        self.tree.heading("code", text="Code")
        self.tree.heading("db_status", text="In DB")
        self.tree.heading("visible", text="Liste")

        self.tree.column("mark", width=36, anchor="center")
        self.tree.column("league_id", width=54, anchor="center")
        self.tree.column("name", width=200)
        self.tree.column("country", width=120)
        self.tree.column("code", width=50)
        self.tree.column("db_status", width=62, anchor="center")
        self.tree.column("visible", width=170)

        ysb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("marked", foreground="green")
        self.tree.tag_configure("unmarked", foreground="gray")

        self.tree.bind("<Button-1>", self._toggle_mark)

        btn_row = tk.Frame(main)
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(btn_row, text="Einlesen", command=self._load_file).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        tk.Button(btn_row, text="Alle markieren", command=lambda: self._set_all(True)).pack(
            side=tk.LEFT, padx=6
        )
        tk.Button(btn_row, text="Keine markieren", command=lambda: self._set_all(False)).pack(
            side=tk.LEFT, padx=6
        )
        tk.Button(
            btn_row,
            text="Markierte importieren …",
            command=self._run_import,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side=tk.RIGHT)

        bf = tk.Frame(main)
        bf.pack(fill=tk.X)
        self._status = tk.Label(bf, text="", fg="gray")
        self._status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(bf, text="Schließen", command=self.destroy).pack(side=tk.RIGHT)

        self.after(120, lambda: self._maybe_autoload())

    def _maybe_autoload(self):
        path = self._path_var.get().strip()
        if path and os.path.isfile(path):
            self._load_file()

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Excel-Datei mit Ligen",
            filetypes=[("Excel", "*.xlsx"), ("Alle", "*.*")],
        )
        if path:
            self._path_var.set(path)
            self._load_file()

    def _refresh_meta(self):
        self._liga128_ids = load_liga128_ids()
        sid = set(self._liga128_ids)
        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cur = conn.execute("SELECT league_id FROM leagues")
            db_ids = {r[0] for r in cur.fetchall()}
            conn.close()
        except Exception:
            db_ids = set()

        self._existing_db.clear()
        for r in self.rows:
            lid = r["league_id"]
            self._existing_db[lid] = lid in db_ids

    def _row_visible_label(self, league_id: int) -> str:
        if league_id in self._liga128_ids:
            return "nur Liga 128"
        return "Tab League"

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._refresh_meta()

        for r in self.rows:
            lid = r["league_id"]
            in_db = "ja" if self._existing_db.get(lid) else "nein"
            vis = self._row_visible_label(lid)
            self.tree.insert(
                "",
                tk.END,
                iid=str(lid),
                values=(
                    "☑",
                    lid,
                    r["league_name"],
                    r["country_name"],
                    r.get("country_code") or "",
                    in_db,
                    vis,
                ),
                tags=("marked",),
            )

    def _load_file(self):
        path = self._path_var.get().strip()
        if not path:
            messagebox.showwarning("Datei fehlt", "Bitte eine .xlsx-Datei auswählen.")
            return
        if not os.path.isfile(path):
            messagebox.showerror("Datei fehlt", f"Pfad nicht gefunden:\n{path}")
            return

        rows, err = parse_leagues_workbook(path)
        if err:
            messagebox.showerror("Excel-Fehler", err)
            return

        self.rows = rows
        self._populate_tree()
        self._status.config(text=f"{len(rows)} Ligen aus Datei gelesen.")

    def _marked_ids(self) -> List[int]:
        out: List[int] = []
        for iid in self.tree.get_children():
            tags = self.tree.item(iid, "tags")
            if tags and tags[0] == "marked":
                out.append(int(iid))
        return out

    def _toggle_mark(self, event):
        region = self.tree.identify_region(event.x, event.y)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        col_id = self.tree.identify_column(event.x)
        if region != "cell" or col_id != "#1":
            return
        tags = self.tree.item(row_id, "tags")
        if tags and tags[0] == "marked":
            self.tree.item(row_id, tags=("unmarked",), values=self._vals_with_mark(row_id, "☐"))
        else:
            self.tree.item(row_id, tags=("marked",), values=self._vals_with_mark(row_id, "☑"))
        return "break"

    def _vals_with_mark(self, row_id: str, mark: str):
        vals = list(self.tree.item(row_id, "values"))
        if vals:
            vals[0] = mark
        return vals

    def _set_all(self, mark: bool):
        for row_id in self.tree.get_children():
            sym = "☑" if mark else "☐"
            tag = "marked" if mark else "unmarked"
            self.tree.item(row_id, tags=(tag,), values=self._vals_with_mark(row_id, sym))

    def _run_import(self):
        lids = self._marked_ids()
        if not lids:
            messagebox.showwarning("Keine Auswahl", "Bitte mindestens eine Liga per Klick auf ✓ markieren.")
            return

        lid_set = set(lids)
        selected_rows = [r for r in self.rows if r["league_id"] in lid_set]
        imported = 0
        skipped = 0

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
        except Exception as e:
            messagebox.showerror("DB-Fehler", str(e))
            return

        for r in sorted(selected_rows, key=lambda x: x["league_id"]):
            dlg = _DestinationChooser(
                self,
                r["league_id"],
                r["league_name"],
                r["country_name"],
            )
            ch = dlg.choice
            if ch == "abort":
                conn.rollback()
                conn.close()
                messagebox.showinfo("Abgebrochen", "Import wurde ohne Speichern der Änderungen abgebrochen.")
                self._populate_tree()
                return
            if ch == "skip":
                skipped += 1
                continue
            upsert_league_row(
                conn,
                int(r["league_id"]),
                str(r["league_name"]),
                str(r["country_name"]),
                str(r.get("country_code") or ""),
            )
            try:
                set_league_visibility_tab(int(r["league_id"]), ch)
            except Exception as exc:
                conn.rollback()
                conn.close()
                messagebox.showerror("Konfiguration", str(exc))
                self._populate_tree()
                return
            imported += 1

        conn.commit()
        conn.close()

        msg = (
            f"Import abgeschlossen.\nImportiert und zugeordnet: {imported}\n"
            f"Übersprungen (pro Liga): {skipped}"
        )
        messagebox.showinfo("Fertig", msg, parent=self)
        self._populate_tree()

        if self.on_finished:
            try:
                self.on_finished()
            except Exception as e:
                print(f"[WARNING] league import on_finished: {e}")


def open_league_import_dialog(parent, db_path: str = "data/flashscore.db", on_finished: DefaultRefresh = None):
    dlg = LeagueImportDialog(parent, db_path=db_path, on_finished=on_finished)
    dlg.lift()
    dlg.focus_force()
