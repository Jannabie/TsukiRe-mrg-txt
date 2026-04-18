#!/usr/bin/env python3
"""
mrg_tool.py — MRG/MZP Script Text Extractor & Repacker
For: Tsukihime Remake (Nintendo Switch) script_text.mrg
Format: mrgd00 / MZP archive

Usage (CLI):
    python mrg_tool.py extract script_text.mrg output.txt
    python mrg_tool.py repack  output.txt script_text_new.mrg

Usage (GUI):
    python mrg_tool.py

Supports: UTF-8 — any language
"""

import io
import json
import os
import re
import struct
import sys
import argparse
import datetime

# ─────────────────────────────────────────────────────────────────────────────
# MZP ARCHIVE PARSER / PACKER
# Based on deepLuna (https://github.com/Hakanaou/deepLuna) by Hakanaou
# ─────────────────────────────────────────────────────────────────────────────

class Mzp:
    MAGIC = b"mrgd00"
    SECTOR_SIZE = 0x800
    HEADER_FORMAT = "<HHHH"

    def __init__(self, path=None, raw=None):
        if path:
            with open(path, "rb") as f:
                raw = f.read()
        assert raw is not None

        magic, entry_count = struct.unpack_from("<6sH", raw, 0)
        assert magic == self.MAGIC, f"Bad magic: {magic!r}"

        self.entry_count = entry_count
        self.headers = []
        self.data = []

        for i in range(entry_count):
            base = 8 + 8 * i
            sec_off, byte_off, size_sec, size_bytes = struct.unpack_from(
                self.HEADER_FORMAT, raw, base)
            self.headers.append((sec_off, byte_off, size_sec, size_bytes))

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
            # Align to 16-byte boundary
            while buf_data.tell() % 16 != 0:
                buf_data.write(b"\xff")

            start = buf_data.tell()
            sec_off = start // cls.SECTOR_SIZE
            byte_off = start % cls.SECTOR_SIZE
            size_sec = len(section) // cls.SECTOR_SIZE
            size_bytes = len(section) & 0xFFFF
            if len(section) % cls.SECTOR_SIZE:
                size_sec += 1

            buf_header.write(struct.pack(cls.HEADER_FORMAT,
                                         sec_off, byte_off, size_sec, size_bytes))
            buf_data.write(section)

        # Pad to 8-byte boundary
        while (buf_header.tell() + buf_data.tell()) % 8 != 0:
            buf_data.write(b"\xff")

        buf_data.seek(0)
        buf_header.write(buf_data.read())
        buf_header.seek(0)
        return buf_header.read()


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACT: MRG → TXT
# ─────────────────────────────────────────────────────────────────────────────

def _load_scene_map():
    """
    Load scene_map.json (sits next to mrg_tool.py) and return:
      offset_to_scene:  {int → (route, day, file)}
      scene_tree:       {route → {day → [file, ...]}}  ordered
      scene_offsets:    {(route, day, file) → [offsets]}
    """
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene_map.json")
    if not os.path.exists(json_path):
        return {}, {}, {}

    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    import re as _re
    offset_to_scene = {}
    scene_offsets   = {}

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

    ROUTE_ORDER = ["Common", "Arcueid", "Ciel", "QA"]

    def day_key(d):
        if not d:
            return -1
        m = _re.search(r"(\d+)", d)
        return int(m.group(1)) if m else 999

    scene_tree = {}
    for sk in scene_offsets:
        route, day, fname = sk
        scene_tree.setdefault(route, {}).setdefault(day, []).append(fname)

    for route in scene_tree:
        for day in scene_tree[route]:
            scene_tree[route][day].sort()
        scene_tree[route] = dict(
            sorted(scene_tree[route].items(), key=lambda x: day_key(x[0]))
        )

    ordered = {}
    for r in ROUTE_ORDER:
        if r in scene_tree:
            ordered[r] = scene_tree[r]

    return offset_to_scene, ordered, scene_offsets


def extract_mrg(mrg_path, txt_path, progress_cb=None):
    """
    Extract all strings from script_text.mrg into a structured .txt file,
    organised by Route → Day → Scene (uses scene_map.json if available,
    otherwise falls back to sequential order).

    [OFFSET:N] markers are preserved for round-trip repacking.
    All comment lines (# …) are ignored during repack.
    """
    if progress_cb:
        progress_cb(0, "Reading MRG file…")

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
        if progress_cb and i % 5000 == 0:
            pct = int(i / offset_count * 60)
            progress_cb(pct, f"Parsing strings… {i}/{offset_count}")

    total = len(strings)
    if progress_cb:
        progress_cb(65, "Loading scene map…")

    offset_to_scene, scene_tree, scene_offsets = _load_scene_map()
    has_map = bool(scene_tree)

    if progress_cb:
        progress_cb(70, f"Writing {total:,} strings…")

    source_name = os.path.basename(mrg_path)
    timestamp   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(txt_path, "w", encoding="utf-8", newline="") as out:
        out.write("# ============================================================\n")
        out.write("# MRG Script Text — Extracted by mrg_tool.py\n")
        out.write(f"# Source   : {source_name}\n")
        out.write(f"# Extracted: {timestamp}\n")
        out.write(f"# Total    : {total:,} strings\n")
        out.write("# ============================================================\n")
        out.write("# EDITING GUIDE\n")
        out.write("#   • Edit the lines between [OFFSET:N] markers freely\n")
        out.write("#   • Do NOT add/remove/reorder [OFFSET:N] header lines\n")
        out.write("#   • Comment lines starting with # are ignored on repack\n")
        out.write("#   • Keep '#' characters inside strings (game line-break)\n")
        out.write("#   • \\r\\n = game line break — keep as-is\n")
        out.write("#   • UTF-8, all languages supported\n")
        out.write("# ============================================================\n\n")

        if has_map:
            ROUTE_ORDER = ["Common", "Arcueid", "Ciel", "QA"]
            written_offsets = set()

            for route in ROUTE_ORDER:
                if route not in scene_tree:
                    continue
                out.write(f"\n# ╔══════════════════════════════════════════════╗\n")
                out.write(f"# ║  ROUTE: {route:<38}║\n")
                out.write(f"# ╚══════════════════════════════════════════════╝\n")

                for day, files in scene_tree[route].items():
                    if day:
                        out.write(f"\n# ── {route} / {day} {'─'*36}\n")
                    for fname in files:
                        sk = (route, day, fname)
                        offsets = sorted(scene_offsets.get(sk, []))
                        if not offsets:
                            continue
                        out.write(f"\n# SCENE: {fname}\n")
                        for offset in offsets:
                            if offset not in strings:
                                continue
                            out.write(f"[OFFSET:{offset}]\n")
                            out.write(strings[offset])
                            out.write("\n")
                            written_offsets.add(offset)

            # Any unmapped offsets at the end
            unmapped = sorted(set(strings.keys()) - written_offsets)
            if unmapped:
                out.write("\n# ── UNMAPPED OFFSETS ──\n")
                for offset in unmapped:
                    out.write(f"[OFFSET:{offset}]\n")
                    out.write(strings[offset])
                    out.write("\n")
        else:
            # Fallback: sequential
            for idx in sorted(strings.keys()):
                out.write(f"[OFFSET:{idx}]\n")
                out.write(strings[idx])
                out.write("\n")

    if progress_cb:
        progress_cb(100, f"Done! {total:,} strings → {os.path.basename(txt_path)}")

    return total


# ─────────────────────────────────────────────────────────────────────────────
# REPACK: TXT → MRG
# ─────────────────────────────────────────────────────────────────────────────

def repack_mrg(txt_path, mrg_out_path, progress_cb=None):
    """
    Repack an edited .txt back into a valid script_text.mrg.

    Reads back [OFFSET:N] blocks, rebuilds the MZP with all 10 sections.
    String length changes are fully supported — offset table is recalculated.
    """
    if progress_cb:
        progress_cb(0, "Reading TXT file…")

    # newline="" preserves \r\n as-is (game strings use CRLF)
    with open(txt_path, "r", encoding="utf-8", newline="") as f:
        raw_text = f.read()

    # Split on [OFFSET:N] markers; skip comment header
    pattern = re.compile(r"^\[OFFSET:(\d+)\]\r?\n", re.MULTILINE)
    parts = pattern.split(raw_text)

    # parts = [preamble, idx, content, idx, content, ...]
    strings = {}
    i = 1
    while i + 1 < len(parts):
        idx = int(parts[i])
        content = parts[i + 1]
        # Strip trailing \n added by extractor (one \n after block)
        if content.endswith("\n"):
            content = content[:-1]
        # Peel off trailing comment lines AND blank separator lines in one pass.
        # They alternate (blank \n then # comment …) in organised-export output.
        # CRITICAL: a whitespace-only game string like "　\r\n" or " \r\n" must
        # NOT be removed — only lines where the printable content is "" OR the
        # line (after stripping \r\n) starts with "#".
        lines = content.splitlines(keepends=True)
        while lines:
            raw = lines[-1].replace("\r", "").replace("\n", "")
            if raw == "" or lines[-1].lstrip("\r\n").startswith("#"):
                lines.pop()
            else:
                break
        content = "".join(lines)
        strings[idx] = content
        i += 2

    if not strings:
        raise ValueError("No [OFFSET:N] entries found in the TXT file.")

    total = len(strings)
    max_offset = max(strings.keys())

    if progress_cb:
        progress_cb(20, f"Rebuilding offset+string tables for {total:,} strings…")

    # ── Build offset table + string table (Big-Endian offsets, UTF-8 data) ──
    offset_table = io.BytesIO()
    string_table = io.BytesIO()

    for offset in range(max_offset + 1):
        text = strings.get(offset, "")
        if not text:
            continue
        offset_table.write(struct.pack(">I", string_table.tell()))
        string_table.write(text.encode("utf-8"))

    # Terminators: final offset written twice + 0xFFFFFFFF sentinel
    end_pos = string_table.tell()
    offset_table.write(struct.pack(">I", end_pos))
    offset_table.write(struct.pack(">I", end_pos))
    offset_table.write(struct.pack(">I", 0xFFFFFFFF))

    offset_table_bytes = offset_table.getvalue()
    string_table_bytes = string_table.getvalue()

    entry_count = max_offset + 1

    if progress_cb:
        progress_cb(50, "Rebuilding padding sections…")

    # ── Newline padding section (  \r\n repeated) ──
    nl_off = io.BytesIO()
    nl_str = io.BytesIO()
    for _ in range(entry_count):
        nl_off.write(struct.pack(">I", nl_str.tell()))
        nl_str.write(b"  \r\n")
    nl_end = nl_str.tell()
    nl_off.write(struct.pack(">I", nl_end))
    nl_off.write(struct.pack(">I", nl_end))
    nl_off.write(struct.pack(">I", 0xFFFFFFFF))
    nl_off_bytes = nl_off.getvalue()
    nl_str_bytes = nl_str.getvalue()

    # ── Space padding section (　\r\n repeated — full-width space) ──
    sp_off = io.BytesIO()
    sp_str = io.BytesIO()
    for _ in range(entry_count):
        sp_off.write(struct.pack(">I", sp_str.tell()))
        sp_str.write("\u3000\r\n".encode("utf-8"))
    sp_end = sp_str.tell()
    sp_off.write(struct.pack(">I", sp_end))
    sp_off.write(struct.pack(">I", sp_end))
    sp_off.write(struct.pack(">I", 0xFFFFFFFF))
    sp_off_bytes = sp_off.getvalue()
    sp_str_bytes = sp_str.getvalue()

    if progress_cb:
        progress_cb(70, "Packing MZP archive…")

    # ── Pack all 10 sections ──
    packed = Mzp.pack([
        offset_table_bytes, string_table_bytes,     # entries 0 & 1: main data
        nl_off_bytes,       nl_str_bytes,            # entries 2 & 3
        sp_off_bytes,       sp_str_bytes,            # entries 4 & 5
        sp_off_bytes,       sp_str_bytes,            # entries 6 & 7
        sp_off_bytes,       sp_str_bytes,            # entries 8 & 9
    ])

    if progress_cb:
        progress_cb(90, f"Writing {len(packed)/1024/1024:.2f} MB → {os.path.basename(mrg_out_path)}…")

    with open(mrg_out_path, "wb") as f:
        f.write(packed)

    if progress_cb:
        progress_cb(100, f"Done! {total:,} strings packed → {os.path.basename(mrg_out_path)}")

    return total, len(packed)


# ─────────────────────────────────────────────────────────────────────────────
# CLI INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

def cli_progress(pct, msg):
    bar_len = 30
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {pct:3d}%  {msg:<50}", end="", flush=True)
    if pct == 100:
        print()


def run_cli():
    parser = argparse.ArgumentParser(
        prog="mrg_tool",
        description="MRG/MZP Script Text Extractor & Repacker (Tsukihime Remake)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mrg_tool.py extract script_text.mrg output.txt
  python mrg_tool.py repack  output.txt  script_text_new.mrg
  python mrg_tool.py gui
        """
    )
    sub = parser.add_subparsers(dest="cmd")

    p_ex = sub.add_parser("extract", help="Extract MRG → TXT")
    p_ex.add_argument("mrg",  help="Input .mrg file")
    p_ex.add_argument("txt",  help="Output .txt file")

    p_rp = sub.add_parser("repack", help="Repack TXT → MRG")
    p_rp.add_argument("txt",     help="Input .txt file (edited)")
    p_rp.add_argument("mrg_out", help="Output .mrg file")

    sub.add_parser("gui", help="Launch GUI")

    args = parser.parse_args()

    if args.cmd == "extract":
        print(f"\n  MRG Extractor — {args.mrg} → {args.txt}")
        count = extract_mrg(args.mrg, args.txt, progress_cb=cli_progress)
        size = os.path.getsize(args.txt)
        print(f"\n  ✓ Extracted {count:,} strings  ({size/1024:.1f} KB)\n")

    elif args.cmd == "repack":
        print(f"\n  MRG Repacker — {args.txt} → {args.mrg_out}")
        count, size = repack_mrg(args.txt, args.mrg_out, progress_cb=cli_progress)
        print(f"\n  ✓ Repacked {count:,} strings  ({size/1024/1024:.2f} MB)\n")

    elif args.cmd == "gui" or args.cmd is None:
        launch_gui()

    else:
        parser.print_help()


# ─────────────────────────────────────────────────────────────────────────────
# GUI INTERFACE (tkinter)
# ─────────────────────────────────────────────────────────────────────────────

def launch_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        print("tkinter not available. Use CLI mode instead.")
        return

    # ── Theme ─────────────────────────────────────────────────────────────
    BG       = "#0f0f14"
    BG2      = "#1a1a24"
    BG3      = "#242434"
    ACCENT   = "#7c5cfc"
    ACCENT2  = "#a07cff"
    FG       = "#e8e8f0"
    FG2      = "#8888aa"
    SUCCESS  = "#4ade80"
    ERR      = "#f87171"
    FONT     = ("Consolas", 10)
    FONT_SM  = ("Consolas", 9)
    FONT_LG  = ("Consolas", 13, "bold")
    FONT_TT  = ("Consolas", 11)

    root = tk.Tk()
    root.title("mrg_tool — MRG Script Text Extractor / Repacker")
    root.configure(bg=BG)
    root.resizable(False, False)

    try:
        root.geometry("700x560")
    except Exception:
        pass

    # ── State variables ────────────────────────────────────────────────────
    mrg_path_var = tk.StringVar()
    txt_path_var = tk.StringVar()
    txt_in_var   = tk.StringVar()
    mrg_out_var  = tk.StringVar()
    status_var   = tk.StringVar(value="Ready.")
    progress_var = tk.DoubleVar(value=0)

    # ── Helpers ────────────────────────────────────────────────────────────
    def pad(w, px=0, py=0):
        w.pack_configure(padx=px, pady=py)

    def label(parent, text, font=FONT, color=FG, **kw):
        l = tk.Label(parent, text=text, font=font, bg=BG, fg=color, **kw)
        return l

    def entry_row(parent, label_text, var, btn_text, btn_cmd):
        row = tk.Frame(parent, bg=BG2, bd=0)
        row.pack(fill="x", padx=0, pady=4)
        tk.Label(row, text=label_text, font=FONT_SM, bg=BG2,
                 fg=FG2, width=14, anchor="w").pack(side="left", padx=(12, 6), pady=8)
        e = tk.Entry(row, textvariable=var, font=FONT_SM, bg=BG3,
                     fg=FG, insertbackground=ACCENT, relief="flat",
                     bd=0, highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BG3)
        e.pack(side="left", fill="x", expand=True, ipady=5, pady=8)
        btn = tk.Button(row, text=btn_text, font=FONT_SM, bg=BG3,
                        fg=ACCENT2, activebackground=ACCENT, activeforeground=FG,
                        relief="flat", bd=0, cursor="hand2",
                        command=btn_cmd, padx=10, pady=3)
        btn.pack(side="left", padx=(8, 12))
        return row

    def big_button(parent, text, cmd, color=ACCENT):
        btn = tk.Button(parent, text=text, font=FONT_LG, bg=color,
                        fg="#ffffff", activebackground=ACCENT2, activeforeground=FG,
                        relief="flat", bd=0, cursor="hand2",
                        command=cmd, padx=24, pady=10)
        return btn

    def set_status(msg, color=FG2):
        status_var.set(msg)
        status_lbl.config(fg=color)
        root.update_idletasks()

    def set_progress(pct, msg):
        progress_var.set(pct)
        status_var.set(msg)
        status_lbl.config(fg=FG2 if pct < 100 else SUCCESS)
        root.update_idletasks()

    # ── Layout ─────────────────────────────────────────────────────────────
    # Title
    hdr = tk.Frame(root, bg=BG, pady=0)
    hdr.pack(fill="x", padx=20, pady=(20, 4))
    tk.Label(hdr, text="◈ mrg_tool", font=("Consolas", 16, "bold"),
             bg=BG, fg=ACCENT).pack(side="left")
    tk.Label(hdr, text="  MRG Script Text Extractor / Repacker",
             font=("Consolas", 10), bg=BG, fg=FG2).pack(side="left")

    divider = tk.Frame(root, bg=ACCENT, height=1)
    divider.pack(fill="x", padx=20, pady=(2, 16))

    # ── EXTRACT SECTION ────────────────────────────────────────────────────
    sec1 = tk.Frame(root, bg=BG2, bd=0, relief="flat")
    sec1.pack(fill="x", padx=20, pady=4)

    sec1_hdr = tk.Frame(sec1, bg=BG2)
    sec1_hdr.pack(fill="x", padx=12, pady=(10, 0))
    tk.Label(sec1_hdr, text="▸ EXTRACT", font=("Consolas", 11, "bold"),
             bg=BG2, fg=ACCENT2).pack(side="left")
    tk.Label(sec1_hdr, text="  MRG → TXT",
             font=FONT_SM, bg=BG2, fg=FG2).pack(side="left")

    def browse_mrg():
        p = filedialog.askopenfilename(
            title="Select script_text.mrg",
            filetypes=[("MRG files", "*.mrg"), ("All files", "*.*")])
        if p:
            mrg_path_var.set(p)
            # Auto-suggest output txt
            base = os.path.splitext(p)[0]
            txt_path_var.set(base + ".txt")

    def browse_txt_out():
        p = filedialog.asksaveasfilename(
            title="Save TXT as…",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if p:
            txt_path_var.set(p)

    entry_row(sec1, "Input .mrg",  mrg_path_var, "Browse…", browse_mrg)
    entry_row(sec1, "Output .txt", txt_path_var,  "Browse…", browse_txt_out)

    def do_extract():
        mrg = mrg_path_var.get().strip()
        txt = txt_path_var.get().strip()
        if not mrg or not os.path.exists(mrg):
            messagebox.showerror("Error", "Please select a valid .mrg file.")
            return
        if not txt:
            messagebox.showerror("Error", "Please specify an output .txt path.")
            return
        btn_extract.config(state="disabled")
        btn_repack.config(state="disabled")
        try:
            count = extract_mrg(mrg, txt, progress_cb=set_progress)
            size = os.path.getsize(txt)
            set_status(
                f"✓ Extracted {count:,} strings → {os.path.basename(txt)}  "
                f"({size/1024:.0f} KB)", SUCCESS)
        except Exception as ex:
            set_status(f"✗ Error: {ex}", ERR)
            messagebox.showerror("Extraction Error", str(ex))
        finally:
            btn_extract.config(state="normal")
            btn_repack.config(state="normal")

    btn_extract = big_button(sec1, "  ⬇  Extract MRG → TXT  ", do_extract)
    btn_extract.pack(pady=(6, 14), padx=12, anchor="e")

    # ── REPACK SECTION ─────────────────────────────────────────────────────
    sep = tk.Frame(root, bg=BG3, height=1)
    sep.pack(fill="x", padx=20, pady=4)

    sec2 = tk.Frame(root, bg=BG2, bd=0, relief="flat")
    sec2.pack(fill="x", padx=20, pady=4)

    sec2_hdr = tk.Frame(sec2, bg=BG2)
    sec2_hdr.pack(fill="x", padx=12, pady=(10, 0))
    tk.Label(sec2_hdr, text="▸ REPACK", font=("Consolas", 11, "bold"),
             bg=BG2, fg=ACCENT2).pack(side="left")
    tk.Label(sec2_hdr, text="  TXT → MRG",
             font=FONT_SM, bg=BG2, fg=FG2).pack(side="left")

    def browse_txt_in():
        p = filedialog.askopenfilename(
            title="Select edited TXT file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if p:
            txt_in_var.set(p)
            base = os.path.splitext(p)[0]
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            mrg_out_var.set(f"{base}_repacked_{ts}.mrg")

    def browse_mrg_out():
        p = filedialog.asksaveasfilename(
            title="Save repacked MRG as…",
            defaultextension=".mrg",
            filetypes=[("MRG files", "*.mrg"), ("All files", "*.*")])
        if p:
            mrg_out_var.set(p)

    entry_row(sec2, "Input .txt",  txt_in_var,  "Browse…", browse_txt_in)
    entry_row(sec2, "Output .mrg", mrg_out_var, "Browse…", browse_mrg_out)

    def do_repack():
        txt = txt_in_var.get().strip()
        mrg = mrg_out_var.get().strip()
        if not txt or not os.path.exists(txt):
            messagebox.showerror("Error", "Please select a valid .txt file.")
            return
        if not mrg:
            messagebox.showerror("Error", "Please specify an output .mrg path.")
            return
        btn_extract.config(state="disabled")
        btn_repack.config(state="disabled")
        try:
            count, size = repack_mrg(txt, mrg, progress_cb=set_progress)
            set_status(
                f"✓ Repacked {count:,} strings → {os.path.basename(mrg)}  "
                f"({size/1024/1024:.2f} MB)", SUCCESS)
        except Exception as ex:
            set_status(f"✗ Error: {ex}", ERR)
            messagebox.showerror("Repack Error", str(ex))
        finally:
            btn_extract.config(state="normal")
            btn_repack.config(state="normal")

    btn_repack = big_button(sec2, "  ⬆  Repack TXT → MRG  ", do_repack, ACCENT)
    btn_repack.pack(pady=(6, 14), padx=12, anchor="e")

    # ── PROGRESS + STATUS ──────────────────────────────────────────────────
    sep2 = tk.Frame(root, bg=BG3, height=1)
    sep2.pack(fill="x", padx=20, pady=(8, 4))

    prog_frame = tk.Frame(root, bg=BG)
    prog_frame.pack(fill="x", padx=20, pady=4)

    style = ttk.Style()
    style.theme_use("default")
    style.configure("TProgressbar", troughcolor=BG3, background=ACCENT,
                    darkcolor=ACCENT, lightcolor=ACCENT, bordercolor=BG3)

    pbar = ttk.Progressbar(prog_frame, variable=progress_var, maximum=100,
                           style="TProgressbar", length=660, mode="determinate")
    pbar.pack(fill="x")

    status_lbl = tk.Label(root, textvariable=status_var, font=FONT_SM,
                          bg=BG, fg=FG2, anchor="w")
    status_lbl.pack(fill="x", padx=20, pady=(2, 6))

    # ── Footer ─────────────────────────────────────────────────────────────
    footer = tk.Frame(root, bg=BG)
    footer.pack(fill="x", padx=20, pady=(0, 12))
    tk.Label(footer,
             text="◦ MZP magic: mrgd00  ◦ UTF-8  ◦ 10-section archive  ◦ Based on deepLuna",
             font=("Consolas", 8), bg=BG, fg=BG3).pack(side="left")

    root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No args → launch GUI
        launch_gui()
    else:
        run_cli()
