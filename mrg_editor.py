#!/usr/bin/env python3
"""
mrg_editor.py — Tsukihime Remake Script Editor
Route-aware GUI editor for script_text.mrg

Features:
  • Route / Day / Scene tree navigation (left panel)
  • Live search across all strings (right panel)
  • In-place string editing
  • Export to organised TXT  |  Repack to .mrg
  • Color-coded by route: Arcueid / Ciel / Common / QA

Usage:
    python mrg_editor.py [script_text.mrg]

Requires: Python 3.8+, tkinter (standard library)
Ships with: scene_map.json (must be in same folder)
"""

import io
import json
import os
import re
import struct
import sys
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ─────────────────────────────────────────────────────────────────────────────
# MZP PARSER / PACKER  (same as mrg_tool.py)
# ─────────────────────────────────────────────────────────────────────────────

class Mzp:
    MAGIC = b"mrgd00"
    SECTOR_SIZE = 0x800
    HEADER_FORMAT = "<HHHH"

    def __init__(self, path=None, raw=None):
        if path:
            with open(path, "rb") as f:
                raw = f.read()
        magic, entry_count = struct.unpack_from("<6sH", raw, 0)
        assert magic == self.MAGIC, f"Bad magic: {magic!r}"
        self.entry_count = entry_count
        self.headers = []
        self.data = []
        for i in range(entry_count):
            base = 8 + 8 * i
            h = struct.unpack_from(self.HEADER_FORMAT, raw, base)
            self.headers.append(h)
        data_start = 8 + 8 * entry_count
        for (sec_off, byte_off, size_sec, size_bytes) in self.headers:
            entry_start = data_start + sec_off * self.SECTOR_SIZE + byte_off
            upper = size_sec * self.SECTOR_SIZE
            size = (upper & ~0xFFFF) | size_bytes
            self.data.append(raw[entry_start: entry_start + size])

    @classmethod
    def pack(cls, sections):
        buf_header = io.BytesIO()
        buf_header.write(struct.pack("<6sH", cls.MAGIC, len(sections)))
        buf_data = io.BytesIO()
        for section in sections:
            while buf_data.tell() % 16 != 0:
                buf_data.write(b"\xff")
            start = buf_data.tell()
            sec_off   = start // cls.SECTOR_SIZE
            byte_off  = start % cls.SECTOR_SIZE
            size_sec  = len(section) // cls.SECTOR_SIZE
            size_bytes = len(section) & 0xFFFF
            if len(section) % cls.SECTOR_SIZE:
                size_sec += 1
            buf_header.write(struct.pack(cls.HEADER_FORMAT, sec_off, byte_off,
                                         size_sec, size_bytes))
            buf_data.write(section)
        while (buf_header.tell() + buf_data.tell()) % 8 != 0:
            buf_data.write(b"\xff")
        buf_data.seek(0)
        buf_header.write(buf_data.read())
        buf_header.seek(0)
        return buf_header.read()


def parse_mrg_strings(mrg_path):
    """Return {offset: text_str} from script_text.mrg"""
    mzp = Mzp(path=mrg_path)
    offsets_raw = mzp.data[0]
    strings_raw = mzp.data[1]
    offset_count = len(offsets_raw) // 4
    strings = {}
    for i in range(offset_count - 1):
        d_start, = struct.unpack(">I", offsets_raw[i * 4: i * 4 + 4])
        d_end_raw = offsets_raw[(i + 1) * 4: (i + 1) * 4 + 4]
        if len(d_end_raw) < 4:
            break
        d_end, = struct.unpack(">I", d_end_raw)
        if d_start == d_end:
            break
        if d_end == 0xFFFFFFFF:
            break
        strings[i] = strings_raw[d_start:d_end].decode("utf-8", errors="replace")
    return strings


def pack_mrg_strings(strings):
    """Return packed bytes for a new script_text.mrg given {offset: text}."""
    max_offset = max(strings.keys())
    offset_table = io.BytesIO()
    string_table = io.BytesIO()
    for offset in range(max_offset + 1):
        text = strings.get(offset, "")
        if not text:
            continue
        offset_table.write(struct.pack(">I", string_table.tell()))
        string_table.write(text.encode("utf-8"))
    end_pos = string_table.tell()
    offset_table.write(struct.pack(">I", end_pos))
    offset_table.write(struct.pack(">I", end_pos))
    offset_table.write(struct.pack(">I", 0xFFFFFFFF))
    ot = offset_table.getvalue()
    st = string_table.getvalue()
    entry_count = max_offset + 1

    def make_pad(text_bytes):
        po, ps = io.BytesIO(), io.BytesIO()
        for _ in range(entry_count):
            po.write(struct.pack(">I", ps.tell()))
            ps.write(text_bytes)
        ep = ps.tell()
        po.write(struct.pack(">I", ep))
        po.write(struct.pack(">I", ep))
        po.write(struct.pack(">I", 0xFFFFFFFF))
        return po.getvalue(), ps.getvalue()

    nl_o, nl_s = make_pad(b"  \r\n")
    sp_o, sp_s = make_pad("\u3000\r\n".encode("utf-8"))
    return Mzp.pack([ot, st, nl_o, nl_s, sp_o, sp_s, sp_o, sp_s, sp_o, sp_s])


# ─────────────────────────────────────────────────────────────────────────────
# SCENE MAP LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_scene_map(json_path=None):
    """
    Load scene_map.json and build:
      offset_to_scene: {int → (route, day, file)}
      scene_tree:      {route → {day → [file, ...]}}  (ordered)
      scene_offsets:   {(route,day,file) → [offset, ...]}  sorted
    """
    if json_path is None:
        # Look next to this script
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene_map.json")

    if not os.path.exists(json_path):
        return {}, {}, {}

    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    offset_to_scene = {}
    scene_offsets = {}

    for key, ranges in raw.items():
        parts = key.split("|")
        route = parts[0]
        day   = parts[1] if len(parts) > 1 else ""
        fname = parts[2] if len(parts) > 2 else ""
        sk = (route, day, fname)
        scene_offsets[sk] = []
        for (start, end) in ranges:
            for o in range(start, end + 1):
                offset_to_scene[o] = sk
                scene_offsets[sk].append(o)

    # Build ordered scene tree
    ROUTE_ORDER = ["Common", "Arcueid", "Ciel", "QA"]
    scene_tree = {}

    def day_sort_key(d):
        if not d:
            return -1
        m = re.search(r"(\d+)", d)
        return int(m.group(1)) if m else 999

    for sk in scene_offsets:
        route, day, fname = sk
        if route not in scene_tree:
            scene_tree[route] = {}
        if day not in scene_tree[route]:
            scene_tree[route][day] = []
        scene_tree[route][day].append(fname)

    # Sort days and files
    for route in scene_tree:
        for day in scene_tree[route]:
            scene_tree[route][day].sort()
        scene_tree[route] = dict(
            sorted(scene_tree[route].items(), key=lambda x: day_sort_key(x[0]))
        )

    ordered_tree = {}
    for route in ROUTE_ORDER:
        if route in scene_tree:
            ordered_tree[route] = scene_tree[route]

    return offset_to_scene, ordered_tree, scene_offsets


# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────────────

ROUTE_COLORS = {
    "Arcueid": "#e05c7a",   # rose-red
    "Ciel":    "#5c9ee0",   # sky-blue
    "Common":  "#8aaa6e",   # muted green
    "QA":      "#c89b40",   # amber
}

PALETTE = {
    "bg":      "#0e0e18",
    "bg2":     "#16161f",
    "bg3":     "#1e1e2d",
    "bg4":     "#26263a",
    "panel":   "#12121c",
    "border":  "#2a2a40",
    "fg":      "#ddddf0",
    "fg2":     "#8888aa",
    "fg3":     "#555577",
    "accent":  "#6655dd",
    "sel_bg":  "#2a2860",
    "sel_fg":  "#ffffff",
    "match":   "#f0b429",   # search match highlight
    "success": "#5adb8a",
    "warn":    "#f87171",
    "font_mono": ("Consolas", 10),
    "font_ui":   ("Consolas", 9),
    "font_h":    ("Consolas", 11, "bold"),
    "font_title":("Consolas", 14, "bold"),
    "font_edit": ("Consolas", 11),
}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

class MrgEditor:
    def __init__(self, root, initial_mrg=None):
        self.root = root
        self.root.title("mrg_editor — Tsukihime Remake Script Editor")
        self.root.configure(bg=PALETTE["bg"])
        self.root.geometry("1180x720")
        self.root.minsize(900, 580)

        # State
        self.strings      = {}           # {offset: text}
        self.mrg_path     = None
        self.offset_to_scene = {}
        self.scene_tree      = {}
        self.scene_offsets   = {}
        self.current_scope   = None      # None = all | (route,day,file) | (route,day,None) | (route,None,None)
        self.search_var      = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.editing_offset  = None      # offset currently in edit box
        self.modified        = False
        self.status_var      = tk.StringVar(value="Open a script_text.mrg to begin.")
        self._filter_job     = None      # debounce timer id

        # Load scene map
        self.offset_to_scene, self.scene_tree, self.scene_offsets = load_scene_map()

        self._build_ui()
        self._apply_ttk_styles()

        if initial_mrg and os.path.exists(initial_mrg):
            self.root.after(100, lambda: self._load_mrg(initial_mrg))

    # ── UI CONSTRUCTION ───────────────────────────────────────────────────

    def _build_ui(self):
        P = PALETTE

        # ── Top bar ──
        topbar = tk.Frame(self.root, bg=P["bg"], height=44)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="◈ mrg_editor", font=P["font_title"],
                 bg=P["bg"], fg=P["accent"]).pack(side="left", padx=(16, 0), pady=8)

        # Toolbar buttons
        btn_cfg = {"font": P["font_ui"], "bg": P["bg4"], "fg": P["fg"],
                   "activebackground": P["accent"], "activeforeground": "#fff",
                   "relief": "flat", "bd": 0, "cursor": "hand2", "padx": 12, "pady": 4}

        tk.Button(topbar, text="⊕  Open MRG", command=self._open_mrg, **btn_cfg
                  ).pack(side="left", padx=(16, 4), pady=6)
        tk.Button(topbar, text="⤓  Export TXT", command=self._export_txt, **btn_cfg
                  ).pack(side="left", padx=4, pady=6)
        tk.Button(topbar, text="⬆  Repack MRG", command=self._repack_mrg, **btn_cfg
                  ).pack(side="left", padx=4, pady=6)

        # Status label (right side of topbar)
        self.status_lbl = tk.Label(topbar, textvariable=self.status_var,
                                   font=P["font_ui"], bg=P["bg"], fg=P["fg2"],
                                   anchor="e")
        self.status_lbl.pack(side="right", padx=16)

        divider = tk.Frame(self.root, bg=P["border"], height=1)
        divider.pack(fill="x", side="top")

        # ── Main paned area ──
        main = tk.Frame(self.root, bg=P["bg"])
        main.pack(fill="both", expand=True)

        # Left panel (tree) — fixed width
        self.left = tk.Frame(main, bg=P["panel"], width=240)
        self.left.pack(side="left", fill="y")
        self.left.pack_propagate(False)

        vdivider = tk.Frame(main, bg=P["border"], width=1)
        vdivider.pack(side="left", fill="y")

        # Right panel
        right = tk.Frame(main, bg=P["bg"])
        right.pack(side="left", fill="both", expand=True)

        self._build_tree(self.left)
        self._build_right(right)

    def _build_tree(self, parent):
        P = PALETTE

        # Header
        hdr = tk.Frame(parent, bg=P["bg3"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="  ROUTES & SCENES", font=P["font_ui"],
                 bg=P["bg3"], fg=P["fg2"]).pack(side="left", padx=6, pady=6)

        btn_all = tk.Button(hdr, text="ALL", font=P["font_ui"],
                            bg=P["bg4"], fg=P["fg2"],
                            activebackground=P["accent"], activeforeground="#fff",
                            relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
                            command=self._show_all)
        btn_all.pack(side="right", padx=6, pady=4)

        # Treeview
        style_name = "RouteTree.Treeview"
        tree_frame = tk.Frame(parent, bg=P["panel"])
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, style=style_name,
                                 show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-1>", self._on_tree_click)

    def _build_right(self, parent):
        P = PALETTE

        # ── Search bar ──
        search_bar = tk.Frame(parent, bg=P["bg2"], height=40)
        search_bar.pack(fill="x")
        search_bar.pack_propagate(False)

        tk.Label(search_bar, text="  🔍", font=("Consolas", 12),
                 bg=P["bg2"], fg=P["fg2"]).pack(side="left", padx=(10, 0), pady=6)

        self.search_entry = tk.Entry(search_bar, textvariable=self.search_var,
                                     font=P["font_edit"], bg=P["bg3"], fg=P["fg"],
                                     insertbackground=P["accent"], relief="flat",
                                     bd=0, highlightthickness=0)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5, pady=6)
        self.search_entry.bind("<Return>", self._search_next)
        self.search_entry.bind("<Escape>", lambda e: (self.search_var.set(""), self.search_entry.event_generate("<<Modified>>")))

        self.match_lbl = tk.Label(search_bar, text="", font=P["font_ui"],
                                  bg=P["bg2"], fg=P["fg2"], width=16, anchor="e")
        self.match_lbl.pack(side="right", padx=12)

        # Scope label
        self.scope_bar = tk.Frame(parent, bg=P["bg3"], height=24)
        self.scope_bar.pack(fill="x")
        self.scope_bar.pack_propagate(False)
        self.scope_lbl = tk.Label(self.scope_bar, text="  Showing: All strings",
                                  font=P["font_ui"], bg=P["bg3"], fg=P["fg2"],
                                  anchor="w")
        self.scope_lbl.pack(fill="x", padx=8)

        # ── String table ──
        table_frame = tk.Frame(parent, bg=P["bg"])
        table_frame.pack(fill="both", expand=True)

        cols = ("offset", "route", "text")
        self.table = ttk.Treeview(table_frame, columns=cols,
                                  show="headings", style="Script.Treeview",
                                  selectmode="browse")
        self.table.heading("offset", text="#", anchor="center")
        self.table.heading("route",  text="Route / Scene",  anchor="w")
        self.table.heading("text",   text="Text",           anchor="w")
        self.table.column("offset", width=60,  minwidth=50,  stretch=False, anchor="center")
        self.table.column("route",  width=220, minwidth=140, stretch=False)
        self.table.column("text",   width=600, minwidth=200, stretch=True)

        vsb2 = ttk.Scrollbar(table_frame, orient="vertical",   command=self.table.yview)
        hsb2 = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side="right", fill="y")
        hsb2.pack(side="bottom", fill="x")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_table_select)
        self.table.bind("<Double-Button-1>", self._on_table_double)

        # ── Edit panel ──
        edit_panel = tk.Frame(parent, bg=P["bg2"], height=160)
        edit_panel.pack(fill="x", side="bottom")
        edit_panel.pack_propagate(False)

        edit_top = tk.Frame(edit_panel, bg=P["bg2"])
        edit_top.pack(fill="x", padx=10, pady=(6, 0))

        self.edit_info = tk.Label(edit_top, text="Select a string to edit",
                                  font=P["font_ui"], bg=P["bg2"], fg=P["fg2"],
                                  anchor="w")
        self.edit_info.pack(side="left", fill="x", expand=True)

        btn_save = tk.Button(edit_top, text="  ✔ Save  ", font=P["font_ui"],
                             bg=P["accent"], fg="#fff",
                             activebackground="#8877ee", activeforeground="#fff",
                             relief="flat", bd=0, cursor="hand2", padx=10, pady=3,
                             command=self._save_edit)
        btn_save.pack(side="right")

        btn_cancel = tk.Button(edit_top, text="  ✖ Cancel  ", font=P["font_ui"],
                               bg=P["bg4"], fg=P["fg2"],
                               activebackground=P["bg3"], activeforeground=P["fg"],
                               relief="flat", bd=0, cursor="hand2", padx=10, pady=3,
                               command=self._cancel_edit)
        btn_cancel.pack(side="right", padx=(0, 6))

        self.edit_box = tk.Text(edit_panel, font=P["font_edit"],
                                bg=P["bg3"], fg=P["fg"],
                                insertbackground=P["accent"],
                                relief="flat", bd=0,
                                highlightthickness=1,
                                highlightbackground=P["border"],
                                highlightcolor=P["accent"],
                                undo=True, wrap="word", height=5)
        self.edit_box.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.edit_box.bind("<Control-Return>", lambda e: self._save_edit())
        self.edit_box.bind("<Escape>", lambda e: self._cancel_edit())

    # ── TTK STYLES ─────────────────────────────────────────────────────────

    def _apply_ttk_styles(self):
        P = PALETTE
        s = ttk.Style()
        s.theme_use("default")

        # Tree (left panel)
        s.configure("RouteTree.Treeview",
                     background=P["panel"], foreground=P["fg"],
                     fieldbackground=P["panel"], borderwidth=0,
                     rowheight=22, font=P["font_ui"])
        s.map("RouteTree.Treeview",
              background=[("selected", P["sel_bg"])],
              foreground=[("selected", P["sel_fg"])])
        s.configure("RouteTree.Treeview.Heading",
                     background=P["bg3"], foreground=P["fg2"],
                     borderwidth=0)

        # Script table (right panel)
        s.configure("Script.Treeview",
                     background=P["bg2"], foreground=P["fg"],
                     fieldbackground=P["bg2"], borderwidth=0,
                     rowheight=20, font=P["font_mono"])
        s.map("Script.Treeview",
              background=[("selected", P["sel_bg"])],
              foreground=[("selected", P["sel_fg"])])
        s.configure("Script.Treeview.Heading",
                     background=P["bg3"], foreground=P["fg2"],
                     font=P["font_ui"], borderwidth=0, relief="flat")
        s.map("Script.Treeview.Heading",
              relief=[("active", "flat")])

        # Scrollbar
        for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            s.configure(name, background=P["bg4"], troughcolor=P["bg2"],
                        bordercolor=P["bg2"], arrowcolor=P["fg3"],
                        relief="flat")

    # ── POPULATE TREE ──────────────────────────────────────────────────────

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.scene_tree:
            return

        for route, days in self.scene_tree.items():
            color = ROUTE_COLORS.get(route, "#aaaaaa")
            route_id = self.tree.insert("", "end", iid=f"R:{route}",
                                        text=f"  ◉  {route}",
                                        tags=(f"route_{route}",))
            self.tree.tag_configure(f"route_{route}", foreground=color)

            for day, files in days.items():
                day_label = day if day else "— root —"
                day_iid = f"D:{route}:{day}"
                day_id = self.tree.insert(route_id, "end", iid=day_iid,
                                          text=f"  ▸  {day_label}",
                                          tags=("day",))
                self.tree.tag_configure("day", foreground=PALETTE["fg2"])

                for fname in files:
                    sk = (route, day, fname)
                    n = len(self.scene_offsets.get(sk, []))
                    short = fname.replace(".txt", "")
                    self.tree.insert(day_id, "end",
                                     iid=f"F:{route}:{day}:{fname}",
                                     text=f"    {short}  ({n})",
                                     tags=("scene",))
                self.tree.tag_configure("scene", foreground=PALETTE["fg3"])

    # ── LOAD / OPEN ────────────────────────────────────────────────────────

    def _open_mrg(self):
        path = filedialog.askopenfilename(
            title="Open script_text.mrg",
            filetypes=[("MRG files", "*.mrg"), ("All files", "*.*")])
        if path:
            self._load_mrg(path)

    def _load_mrg(self, path):
        self._set_status("Loading…", PALETTE["fg2"])
        self.root.update_idletasks()
        try:
            self.strings  = parse_mrg_strings(path)
            self.mrg_path = path
            self.modified = False
            self._populate_tree()
            self._show_all()
            name = os.path.basename(path)
            self._set_status(f"Loaded {len(self.strings):,} strings — {name}",
                             PALETTE["success"])
            self.root.title(f"mrg_editor  —  {name}")
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self._set_status(f"Error: {ex}", PALETTE["warn"])

    # ── TABLE POPULATION ───────────────────────────────────────────────────

    def _show_all(self):
        self.current_scope = None
        self.scope_lbl.config(text="  Showing: All strings")
        self._populate_table()

    def _populate_table(self, search_text=""):
        self.table.delete(*self.table.get_children())
        if not self.strings:
            return

        # Determine which offsets to show
        if self.current_scope is None:
            offsets = sorted(self.strings.keys())
        else:
            route, day, fname = self.current_scope
            offsets = []
            for sk, os_list in self.scene_offsets.items():
                r, d, f = sk
                match = (r == route and
                         (day  is None or d == day) and
                         (fname is None or f == fname))
                if match:
                    offsets.extend(os_list)
            offsets = sorted(set(offsets))

        # Apply search filter
        sq = search_text.strip().lower()
        matched = 0
        for offset in offsets:
            text = self.strings.get(offset, "")
            if sq and sq not in text.lower():
                continue
            matched += 1
            sk = self.offset_to_scene.get(offset, (None, None, None))
            route_name = sk[0] or "?"
            scene_name = sk[2].replace(".txt", "") if sk[2] else ""
            day_part   = sk[1] if sk[1] else ""
            if day_part:
                route_col = f"{route_name} / {day_part}"
            else:
                route_col = route_name
            display = text.replace("\r\n", " ↵ ").replace("\n", " ↵ ").strip()[:120]
            color = ROUTE_COLORS.get(route_name, PALETTE["fg3"])
            self.table.insert("", "end",
                              iid=f"S:{offset}",
                              values=(offset, f"{route_col} › {scene_name}", display),
                              tags=(f"rt_{route_name}",))
            self.table.tag_configure(f"rt_{route_name}",
                                     foreground=color)

        total_shown = len(offsets)
        if sq:
            self.match_lbl.config(text=f"{matched:,} / {total_shown:,} matches",
                                  fg=PALETTE["match"] if matched else PALETTE["warn"])
        else:
            self.match_lbl.config(text=f"{total_shown:,} strings", fg=PALETTE["fg2"])

    # ── EVENT HANDLERS ─────────────────────────────────────────────────────

    def _on_tree_click(self, event):
        # Allow collapsing route nodes without triggering select
        pass

    def _on_tree_select(self, event):
        sel = self.tree.focus()
        if not sel:
            return

        if sel.startswith("R:"):
            route = sel[2:]
            self.current_scope = (route, None, None)
            self.scope_lbl.config(
                text=f"  Route: {route}",
                fg=ROUTE_COLORS.get(route, PALETTE["fg2"]))
        elif sel.startswith("D:"):
            _, route, day = sel.split(":", 2)
            self.current_scope = (route, day, None)
            label = f"  {route}  /  {day}" if day else f"  {route}  / root"
            self.scope_lbl.config(text=label,
                                  fg=ROUTE_COLORS.get(route, PALETTE["fg2"]))
        elif sel.startswith("F:"):
            _, route, day, fname = sel.split(":", 3)
            self.current_scope = (route, day, fname)
            short = fname.replace(".txt", "")
            label = f"  {route}  /  {day}  /  {short}" if day else f"  {route}  /  {short}"
            self.scope_lbl.config(text=label,
                                  fg=ROUTE_COLORS.get(route, PALETTE["fg2"]))

        self._populate_table(self.search_var.get())

    def _on_search_change(self, *args):
        # Debounce 150ms
        if self._filter_job:
            self.root.after_cancel(self._filter_job)
        self._filter_job = self.root.after(150, self._do_filter)

    def _do_filter(self):
        self._populate_table(self.search_var.get())

    def _search_next(self, event=None):
        """Jump to next search match."""
        children = self.table.get_children()
        if not children:
            return
        sel = self.table.focus()
        if sel in children:
            idx = children.index(sel)
            nxt = children[(idx + 1) % len(children)]
        else:
            nxt = children[0]
        self.table.selection_set(nxt)
        self.table.focus(nxt)
        self.table.see(nxt)

    def _on_table_select(self, event):
        sel = self.table.focus()
        if not sel or not sel.startswith("S:"):
            return
        offset = int(sel[2:])
        self._load_edit(offset)

    def _on_table_double(self, event):
        self.edit_box.focus_set()

    # ── EDIT PANEL ─────────────────────────────────────────────────────────

    def _load_edit(self, offset):
        if offset not in self.strings:
            return
        self.editing_offset = offset
        sk = self.offset_to_scene.get(offset, (None, None, None))
        route, day, fname = sk
        color  = ROUTE_COLORS.get(route, PALETTE["fg2"])
        loc_parts = [p for p in [route, day, fname] if p]
        self.edit_info.config(
            text=f"  Editing offset #{offset}   •   {'  /  '.join(loc_parts)}",
            fg=color)
        self.edit_box.config(state="normal")
        self.edit_box.delete("1.0", "end")
        self.edit_box.insert("1.0", self.strings[offset])
        self.edit_box.edit_reset()

    def _save_edit(self):
        if self.editing_offset is None:
            return
        new_text = self.edit_box.get("1.0", "end-1c")
        self.strings[self.editing_offset] = new_text
        self.modified = True

        # Update table row
        iid = f"S:{self.editing_offset}"
        if self.table.exists(iid):
            display = new_text.replace("\r\n", " ↵ ").replace("\n", " ↵ ").strip()[:120]
            vals = list(self.table.item(iid, "values"))
            vals[2] = display
            self.table.item(iid, values=vals)

        self._set_status(f"Saved offset #{self.editing_offset} — {len(new_text)} chars",
                         PALETTE["success"])
        self.edit_info.config(text=f"  Offset #{self.editing_offset} saved ✔",
                              fg=PALETTE["success"])

    def _cancel_edit(self):
        if self.editing_offset is not None:
            self._load_edit(self.editing_offset)  # reload original

    # ── EXPORT TXT ─────────────────────────────────────────────────────────

    def _export_txt(self):
        if not self.strings:
            messagebox.showwarning("No data", "No strings loaded. Open a .mrg first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export TXT",
            defaultextension=".txt",
            initialfile="script_text_export.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        self._set_status("Exporting…", PALETTE["fg2"])
        self.root.update_idletasks()
        try:
            count = self._write_organised_txt(path)
            self._set_status(f"Exported {count:,} strings → {os.path.basename(path)}",
                             PALETTE["success"])
        except Exception as ex:
            messagebox.showerror("Export Error", str(ex))
            self._set_status(f"Error: {ex}", PALETTE["warn"])

    def _write_organised_txt(self, path):
        """Write an organised, route/day/scene grouped TXT."""
        ROUTE_ORDER = ["Common", "Arcueid", "Ciel", "QA"]
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(path, "w", encoding="utf-8", newline="") as out:
            out.write("# ============================================================\n")
            out.write("# MRG Script Text — Organised Export\n")
            out.write(f"# Exported: {ts}  |  Strings: {len(self.strings):,}\n")
            out.write("# RULES: Do NOT add/remove [OFFSET:N] lines.\n")
            out.write("#        Edit only the text between them.\n")
            out.write("#        Keep '#' characters (game line-break marker).\n")
            out.write("# ============================================================\n\n")

            written = 0

            for route in ROUTE_ORDER:
                if route not in self.scene_tree:
                    continue
                rc = ROUTE_COLORS.get(route, "#")
                out.write(f"\n# ╔══════════════════════════════════════════════════╗\n")
                out.write(f"# ║  ROUTE: {route:<44}║\n")
                out.write(f"# ╚══════════════════════════════════════════════════╝\n")

                for day, files in self.scene_tree[route].items():
                    if day:
                        out.write(f"\n# ── {route} / {day} ────────────────────────────────\n")
                    for fname in files:
                        sk = (route, day, fname)
                        offsets = sorted(self.scene_offsets.get(sk, []))
                        if not offsets:
                            continue
                        out.write(f"\n# SCENE: {fname}\n")
                        for offset in offsets:
                            text = self.strings.get(offset, "")
                            out.write(f"[OFFSET:{offset}]\n")
                            out.write(text)
                            out.write("\n")
                            written += 1

        return written

    # ── REPACK MRG ─────────────────────────────────────────────────────────

    def _repack_mrg(self):
        if not self.strings:
            messagebox.showwarning("No data", "No strings loaded.")
            return
        path = filedialog.asksaveasfilename(
            title="Save repacked MRG as…",
            defaultextension=".mrg",
            initialfile="script_text_repacked.mrg",
            filetypes=[("MRG files", "*.mrg"), ("All files", "*.*")])
        if not path:
            return
        self._set_status("Repacking…", PALETTE["fg2"])
        self.root.update_idletasks()
        try:
            packed = pack_mrg_strings(self.strings)
            with open(path, "wb") as f:
                f.write(packed)
            sz = len(packed) / 1024 / 1024
            self.modified = False
            self._set_status(
                f"Repacked {len(self.strings):,} strings  ({sz:.2f} MB) → {os.path.basename(path)}",
                PALETTE["success"])
        except Exception as ex:
            messagebox.showerror("Repack Error", str(ex))
            self._set_status(f"Error: {ex}", PALETTE["warn"])

    # ── HELPERS ────────────────────────────────────────────────────────────

    def _set_status(self, msg, color=None):
        self.status_var.set(msg)
        if color:
            self.status_lbl.config(fg=color)
        self.root.update_idletasks()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    app = MrgEditor(root, initial_mrg=initial)
    root.mainloop()


if __name__ == "__main__":
    main()
