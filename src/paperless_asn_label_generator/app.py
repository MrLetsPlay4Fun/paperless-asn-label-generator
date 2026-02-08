#!/usr/bin/env python3
"""
paperless-ngx ASN Label Generator (GUI) + Calibration

This version adds calibration controls to fix typical "top row too low / bottom row too high"
and left/right drift issues when printing on real label sheets (e.g. Avery Zweckform L4731/L4731REV).

New controls:
- Offset X/Y (mm): shifts the whole grid
- Spalten-Pitch Δ (mm): changes distance between columns (fixes left/right drift)
- Zeilen-Pitch Δ (mm): changes distance between rows (fixes top/bottom drift)

Tip: In your PDF viewer / printer settings, print at 100% (no "Fit to page"/"Shrink/Expand").
"""

from __future__ import annotations

import math
import os
import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode import code128

import qrcode
from PIL import Image, ImageTk

from . import __version__


BarcodeKind = Literal["QR", "CODE128"]


@dataclass(frozen=True)
class SheetLayout:
    name: str
    cols: int
    rows: int
    label_w: float  # points
    label_h: float  # points
    gap_x: float    # points  (base gap)
    gap_y: float    # points  (base gap)
    margin_left: float  # points
    margin_top: float   # points

    @property
    def labels_per_page(self) -> int:
        return self.cols * self.rows

    @property
    def pitch_x(self) -> float:
        return self.label_w + self.gap_x

    @property
    def pitch_y(self) -> float:
        return self.label_h + self.gap_y


# NOTE: Many shops/templates call this "L4731" (25.4 x 10mm, 7x27 = 189 labels).
# If your sheet is slightly different, use calibration below.
AVERY_L4731 = SheetLayout(
    name="Avery Zweckform L4731 / L4731REV (7x27, 25.4mm x 10mm)",
    cols=7,
    rows=27,
    label_w=25.4 * mm,
    label_h=10.0 * mm,
    gap_x=0.25 * cm,   # base guess (tweak with Δ if needed)
    gap_y=0.0 * cm,    # base guess (tweak with Δ if needed)
    margin_left=0.85 * cm,
    margin_top=1.35 * cm,
)


def make_asn_text(prefix: str, number: int, leading_zeros: int) -> str:
    return f"{prefix}{number:0{leading_zeros}d}"


def make_qr_image(data: str, target_px: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((target_px, target_px), Image.Resampling.LANCZOS)


def draw_label(
    c: rl_canvas.Canvas,
    x: float,
    y: float,
    layout: SheetLayout,
    text: str,
    kind: BarcodeKind,
    draw_border: bool,
) -> None:
    """Draw one label in the rectangle [x, y, label_w, label_h] (origin bottom-left)."""
    if draw_border:
        c.rect(x, y, layout.label_w, layout.label_h, stroke=1, fill=0)

    pad = 1.0 * mm

    code_size = layout.label_h * 0.90
    code_x = x + pad
    code_y = y + (layout.label_h - code_size) / 2.0

    if kind == "QR":
        dpi = 600
        target_px = max(80, int(code_size * dpi / 72.0))
        img = make_qr_image(text, target_px)
        c.drawImage(ImageReader(img), code_x, code_y, width=code_size, height=code_size, preserveAspectRatio=True, mask=None)
    else:
        b = code128.Code128(text, barHeight=code_size * 0.85, humanReadable=False)
        desired_w = code_size
        scale = min(1.0, desired_w / float(b.width))
        c.saveState()
        c.translate(code_x, code_y + (code_size - b.barHeight) / 2.0)
        c.scale(scale, 1.0)
        b.drawOn(c, 0, 0)
        c.restoreState()

    text_x = code_x + code_size + pad
    font_size = max(5.5, min(8.0, (layout.label_h / mm) * 0.55))
    c.setFont("Helvetica", font_size)
    c.drawString(text_x, y + (layout.label_h - font_size) / 2.0, text)


def generate_pdf(
    output_path: str,
    start_number: int,
    count: int,
    prefix: str,
    leading_zeros: int,
    kind: BarcodeKind,
    layout: SheetLayout = AVERY_L4731,
    draw_border: bool = False,
    # NEW calibration:
    offset_x_mm: float = 0.0,         # + moves right
    offset_y_mm: float = 0.0,         # + moves up
    pitch_dx_mm: float = 0.0,         # added to pitch_x (distance between columns)
    pitch_dy_mm: float = 0.0,         # added to pitch_y (distance between rows)
) -> Tuple[int, int]:
    """
    Returns: (pages_generated, next_number)
    """
    if count <= 0:
        raise ValueError("count must be > 0")
    if start_number <= 0:
        raise ValueError("start_number must be > 0")
    if leading_zeros < 0:
        raise ValueError("leading_zeros must be >= 0")
    if not prefix:
        raise ValueError("prefix must not be empty")

    _page_w, page_h = A4
    labels_per_page = layout.labels_per_page
    pages = math.ceil(count / labels_per_page)

    # Effective pitch + offsets (points)
    pitch_x = layout.pitch_x + (pitch_dx_mm * mm)
    pitch_y = layout.pitch_y + (pitch_dy_mm * mm)
    off_x = offset_x_mm * mm
    off_y = offset_y_mm * mm

    c = rl_canvas.Canvas(output_path, pagesize=A4)

    current = start_number
    remaining = count

    for _ in range(pages):
        n_this_page = min(remaining, labels_per_page)

        for i in range(n_this_page):
            r = i // layout.cols
            col = i % layout.cols

            x = layout.margin_left + col * pitch_x + off_x
            y = page_h - layout.margin_top - layout.label_h - r * pitch_y + off_y

            text = make_asn_text(prefix, current, leading_zeros)
            draw_label(c, x, y, layout, text, kind, draw_border)

            current += 1

        c.showPage()
        remaining -= n_this_page

    c.save()
    return pages, current

DEFAULT_SETTINGS = {
    "start": "1",
    "mode": "labels",
    "count": str(AVERY_L4731.labels_per_page),
    "pages": "1",
    "prefix": "ASN",
    "zeros": "7",
    "kind": "QR",
    "border": False,
    # neutrale Kalibrierung für frische Installationen
    "off_x": "0.0",
    "off_y": "0.0",
    "pitch_dx": "0.0",
    "pitch_dy": "0.0",
}

# Effektive Basiswerte, die beim Drucken intern immer addiert werden.
BASE_CALIBRATION_MM = {
    "off_x": -4.5,
    "off_y": 7.0,
    "pitch_dx": 1.2,
    "pitch_dy": 0.42,
}

class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master

        self.var_start = tk.StringVar(value=DEFAULT_SETTINGS["start"])
        self.var_mode = tk.StringVar(value=DEFAULT_SETTINGS["mode"])
        self.var_count = tk.StringVar(value=DEFAULT_SETTINGS["count"])
        self.var_pages = tk.StringVar(value=DEFAULT_SETTINGS["pages"])
        self.var_prefix = tk.StringVar(value=DEFAULT_SETTINGS["prefix"])
        self.var_zeros = tk.StringVar(value=DEFAULT_SETTINGS["zeros"])
        self.var_kind = tk.StringVar(value=DEFAULT_SETTINGS["kind"])
        self.var_border = tk.BooleanVar(value=DEFAULT_SETTINGS["border"])
        self.var_off_x = tk.StringVar(value=DEFAULT_SETTINGS["off_x"])
        self.var_off_y = tk.StringVar(value=DEFAULT_SETTINGS["off_y"])
        self.var_pitch_dx = tk.StringVar(value=DEFAULT_SETTINGS["pitch_dx"])
        self.var_pitch_dy = tk.StringVar(value=DEFAULT_SETTINGS["pitch_dy"])

        self._preview_imgtk: ImageTk.PhotoImage | None = None
        self._count_entry: ttk.Entry | None = None
        self._pages_entry: ttk.Entry | None = None

        self._loading_settings = False
        self._save_job = None
        self._pending_config_status: str | None = None

        # 1) Laden (überschreibt Defaults, falls config existiert)
        self._load_settings()

        # UI einmal bauen
        self._build_ui()
        self._flush_pending_config_status()
        self._apply_mode()
        self._update_preview()

        # 2) Autosave aktivieren
        self._install_autosave_traces()


    def _config_path(self) -> Path:
        """
        Cross-platform config path:
        - Windows: %APPDATA%/paperless-ngx-asn-labels/config.json
        - macOS: ~/Library/Application Support/paperless-ngx-asn-labels/config.json
        - Linux: $XDG_CONFIG_HOME/paperless-ngx-asn-labels/config.json  (fallback ~/.config/...)
        """
        home = Path.home()

        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = home / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))

        return base / "paperless-ngx-asn-labels" / "config.json"

    def _settings_to_dict(self) -> dict:
        return {
            "start": self.var_start.get(),
            "mode": self.var_mode.get(),
            "count": self.var_count.get(),
            "pages": self.var_pages.get(),
            "prefix": self.var_prefix.get(),
            "zeros": self.var_zeros.get(),
            "kind": self.var_kind.get(),
            "border": bool(self.var_border.get()),
            "off_x": self.var_off_x.get(),
            "off_y": self.var_off_y.get(),
            "pitch_dx": self.var_pitch_dx.get(),
            "pitch_dy": self.var_pitch_dy.get(),
            "calibration_mode": "delta",
        }

    def _apply_settings_from_dict(self, d: dict) -> None:
        # Beim Laden sollen keine Autosaves getriggert werden
        self._loading_settings = True
        try:
            calibration_mode = str(d.get("calibration_mode", "")).strip().lower()
            legacy_absolute = calibration_mode != "delta"
            if calibration_mode == "":
                # Übergangsfall: Wenn alle Werte 0 sind (vorherige Zwischenversion), als Delta interpretieren.
                parsed = [self._coerce_float(d.get(k)) for k in ("off_x", "off_y", "pitch_dx", "pitch_dy") if k in d]
                if parsed and all(v is not None and abs(v) < 1e-9 for v in parsed):
                    legacy_absolute = False

            def set_calibration_var(key: str, var: tk.StringVar) -> None:
                if key not in d:
                    return
                if legacy_absolute:
                    absolute = self._coerce_float(d.get(key))
                    if absolute is not None:
                        var.set(str(absolute - BASE_CALIBRATION_MM[key]))
                        return
                var.set(str(d[key]))

            if "start" in d: self.var_start.set(str(d["start"]))
            if "mode" in d: self.var_mode.set(str(d["mode"]))
            if "count" in d: self.var_count.set(str(d["count"]))
            if "pages" in d: self.var_pages.set(str(d["pages"]))
            if "prefix" in d: self.var_prefix.set(str(d["prefix"]))
            if "zeros" in d: self.var_zeros.set(str(d["zeros"]))
            if "kind" in d: self.var_kind.set(str(d["kind"]))
            if "border" in d: self.var_border.set(bool(d["border"]))
            set_calibration_var("off_x", self.var_off_x)
            set_calibration_var("off_y", self.var_off_y)
            set_calibration_var("pitch_dx", self.var_pitch_dx)
            set_calibration_var("pitch_dy", self.var_pitch_dy)
        finally:
            self._loading_settings = False

    def _load_settings(self) -> None:
        path = self._config_path()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._apply_settings_from_dict(data)
                else:
                    self._set_config_status(f"⚠️ Config hat falsches Format, verwende Defaults: {path}")
        except Exception as e:
            # GUI bleibt benutzbar, Fehler wird aber sichtbar gemacht
            self._set_config_status(f"⚠️ Config konnte nicht geladen werden ({path}): {e}")

    def _save_settings_now(self) -> None:
        if getattr(self, "_loading_settings", False):
            return
        path = self._config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._settings_to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
            self._set_config_status("")
        except Exception as e:
            self._set_config_status(f"⚠️ Config konnte nicht gespeichert werden ({path}): {e}")

    def _schedule_save(self) -> None:
        # Debounce: erst nach kurzer Pause speichern
        if getattr(self, "_loading_settings", False):
            return
        if getattr(self, "_save_job", None) is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(500, self._save_settings_now)

    def _install_autosave_traces(self) -> None:
        # alle Variablen bei Änderung -> save schedulen
        vars_to_watch = [
            self.var_start,
            self.var_mode,
            self.var_count,
            self.var_pages,
            self.var_prefix,
            self.var_zeros,
            self.var_kind,
            self.var_border,
            self.var_off_x,
            self.var_off_y,
            self.var_pitch_dx,
            self.var_pitch_dy,
        ]
        for v in vars_to_watch:
            try:
                v.trace_add("write", lambda *_: self._schedule_save())
            except Exception:
                # fallback (sehr alte Tk-Versionen)
                v.trace("w", lambda *_: self._schedule_save())

    def _build_ui(self) -> None:
        self.master.title(f"paperless-ngx ASN Label Generator v{__version__} (A4 / Avery L4731) - mit Kalibrierung")
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        frm = ttk.LabelFrame(self, text="Einstellungen")
        frm.grid(row=0, column=0, sticky="nsew")
        for i in range(4):
            frm.columnconfigure(i, weight=1)

        def add_row(label: str, var: tk.StringVar, row: int, hint: str = "", store: str | None = None) -> None:
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", padx=(10, 6), pady=6)
            ent = ttk.Entry(frm, textvariable=var, width=14)
            ent.grid(row=row, column=1, sticky="we", padx=(0, 10), pady=6)
            if hint:
                ttk.Label(frm, text=hint, foreground="#555").grid(row=row, column=2, columnspan=2, sticky="w", padx=(0, 10), pady=6)
            ent.bind("<KeyRelease>", lambda _e: self._update_preview())
            if store == "count":
                self._count_entry = ent
            elif store == "pages":
                self._pages_entry = ent

        add_row("Start-Nummer", self.var_start, 0, "z.B. 1 oder 190")

        ttk.Label(frm, text="Menge als").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=6)
        mode_box = ttk.Frame(frm)
        mode_box.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=6)
        ttk.Radiobutton(mode_box, text="Labels", value="labels", variable=self.var_mode, command=self._apply_mode).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(mode_box, text="A4 Blätter", value="pages", variable=self.var_mode, command=self._apply_mode).pack(side="left")

        add_row("Anzahl Labels", self.var_count, 2, f"{AVERY_L4731.labels_per_page} Labels pro A4-Seite", store="count")
        add_row("Anzahl A4 Blätter", self.var_pages, 3, "z.B. 3 → erzeugt 3 Seiten", store="pages")

        add_row("Prefix", self.var_prefix, 4, "Muss zu PAPERLESS_CONSUMER_ASN_BARCODE_PREFIX passen")
        add_row("Führende Nullen", self.var_zeros, 5, "z.B. 5 → ASN00001")

        ttk.Label(frm, text="Code-Typ").grid(row=6, column=0, sticky="w", padx=(10, 6), pady=6)
        cmb = ttk.Combobox(frm, textvariable=self.var_kind, values=["QR", "CODE128"], state="readonly", width=12)
        cmb.grid(row=6, column=1, sticky="w", padx=(0, 10), pady=6)
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._update_preview())

        chk = ttk.Checkbutton(frm, text="Rahmen um Labels zeichnen (Kalibrierung)", variable=self.var_border, command=self._update_preview)
        chk.grid(row=6, column=2, columnspan=2, sticky="w", padx=(0, 10), pady=6)

        cal = ttk.LabelFrame(frm, text="Kalibrierung (mm)")
        cal.grid(row=7, column=0, columnspan=4, sticky="we", padx=10, pady=(10, 6))
        for i in range(6):
            cal.columnconfigure(i, weight=1)

        def add_cal(label: str, var: tk.StringVar, col: int, hint: str) -> None:
            ttk.Label(cal, text=label).grid(row=0, column=col, sticky="w", padx=(6, 4), pady=6)
            e = ttk.Entry(cal, textvariable=var, width=10)
            e.grid(row=0, column=col + 1, sticky="we", padx=(0, 10), pady=6)
            e.bind("<KeyRelease>", lambda _e: self._update_preview())
            ttk.Label(cal, text=hint, foreground="#555").grid(row=0, column=col + 2, sticky="w", padx=(0, 10), pady=6)

        add_cal("Offset X", self.var_off_x, 0, "+ rechts")
        add_cal("Offset Y", self.var_off_y, 3, "+ hoch")

        def add_cal2(label: str, var: tk.StringVar, row: int, col: int, hint: str) -> None:
            ttk.Label(cal, text=label).grid(row=row, column=col, sticky="w", padx=(6, 4), pady=6)
            e = ttk.Entry(cal, textvariable=var, width=10)
            e.grid(row=row, column=col + 1, sticky="we", padx=(0, 10), pady=6)
            e.bind("<KeyRelease>", lambda _e: self._update_preview())
            ttk.Label(cal, text=hint, foreground="#555").grid(row=row, column=col + 2, sticky="w", padx=(0, 10), pady=6)

        add_cal2("Spalten-Pitch Δ", self.var_pitch_dx, 1, 0, "→ drift links/rechts")
        add_cal2("Zeilen-Pitch Δ", self.var_pitch_dy, 1, 3, "→ top/bottom drift")

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(right, text="Vorschau (1 Label)").grid(row=0, column=0, sticky="w")

        self.preview = ttk.Label(right)
        self.preview.grid(row=1, column=0, sticky="nsew", pady=(6, 10))

        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, sticky="we")
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="PDF erzeugen…", command=self.on_generate_pdf).grid(row=0, column=0, sticky="we", padx=(0, 6))
        ttk.Button(btns, text="Ordner öffnen", command=self.on_open_folder).grid(row=0, column=1, sticky="we", padx=(6, 0))

        ttk.Button(btns, text="Config löschen", command=self.on_reset_config).grid(
            row=1, column=0, columnspan=2, sticky="we", pady=(6, 0)
        )

        self.lbl_status = ttk.Label(self, text="", foreground="#333")
        self.lbl_status.grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 0))
        self.lbl_config_status = ttk.Label(self, text="", foreground="#b00020")
        self.lbl_config_status.grid(row=2, column=0, columnspan=2, sticky="we", pady=(4, 0))

    def _set_config_status(self, message: str) -> None:
        lbl = getattr(self, "lbl_config_status", None)
        if lbl is None:
            self._pending_config_status = message
            return
        lbl.configure(text=message)
        self._pending_config_status = message

    def _flush_pending_config_status(self) -> None:
        if self._pending_config_status is not None:
            self._set_config_status(self._pending_config_status)

    def _apply_mode(self) -> None:
        mode = self.var_mode.get()
        if self._count_entry is not None:
            self._count_entry.configure(state=("normal" if mode == "labels" else "disabled"))
        if self._pages_entry is not None:
            self._pages_entry.configure(state=("normal" if mode == "pages" else "disabled"))
        self._update_preview()

    def _parse_int(self, s: str, field: str) -> int:
        try:
            v = int(s.strip())
        except Exception:
            raise ValueError(f"{field} ist keine gültige Zahl.")
        return v

    def _parse_float(self, s: str, field: str) -> float:
        try:
            return float(s.strip().replace(",", "."))
        except Exception:
            raise ValueError(f"{field} ist keine gültige Zahl (z.B. 0.2).")

    def _coerce_float(self, value: object) -> float | None:
        try:
            return float(str(value).strip().replace(",", "."))
        except Exception:
            return None

    def _effective_count_and_pages(self) -> tuple[int, int]:
        mode = self.var_mode.get()
        if mode == "pages":
            pages = self._parse_int(self.var_pages.get(), "Anzahl A4 Blätter")
            if pages <= 0:
                raise ValueError("Anzahl A4 Blätter muss > 0 sein.")
            count = pages * AVERY_L4731.labels_per_page
            return count, pages
        else:
            count = self._parse_int(self.var_count.get(), "Anzahl Labels")
            if count <= 0:
                raise ValueError("Anzahl Labels muss > 0 sein.")
            pages = math.ceil(count / AVERY_L4731.labels_per_page)
            return count, pages

    def _current_text(self) -> str:
        start = self._parse_int(self.var_start.get(), "Start-Nummer")
        zeros = self._parse_int(self.var_zeros.get(), "Führende Nullen")
        prefix = self.var_prefix.get().strip()
        if not prefix:
            raise ValueError("Prefix darf nicht leer sein.")
        if start <= 0:
            raise ValueError("Start-Nummer muss > 0 sein.")
        if zeros < 0:
            raise ValueError("Führende Nullen muss >= 0 sein.")
        return make_asn_text(prefix, start, zeros)

    def _calibration_delta(self) -> tuple[float, float, float, float]:
        off_x = self._parse_float(self.var_off_x.get(), "Offset X")
        off_y = self._parse_float(self.var_off_y.get(), "Offset Y")
        pdx = self._parse_float(self.var_pitch_dx.get(), "Spalten-Pitch Δ")
        pdy = self._parse_float(self.var_pitch_dy.get(), "Zeilen-Pitch Δ")
        return off_x, off_y, pdx, pdy

    def _calibration(self) -> tuple[float, float, float, float]:
        off_x_delta, off_y_delta, pdx_delta, pdy_delta = self._calibration_delta()
        return (
            BASE_CALIBRATION_MM["off_x"] + off_x_delta,
            BASE_CALIBRATION_MM["off_y"] + off_y_delta,
            BASE_CALIBRATION_MM["pitch_dx"] + pdx_delta,
            BASE_CALIBRATION_MM["pitch_dy"] + pdy_delta,
        )

    def _update_preview(self, *_args) -> None:
        try:
            text = self._current_text()
            kind: BarcodeKind = "QR" if self.var_kind.get() == "QR" else "CODE128"
            img = self._render_preview_image(text, kind, self.var_border.get())
            self._preview_imgtk = ImageTk.PhotoImage(img)
            self.preview.configure(image=self._preview_imgtk)

            count, pages = self._effective_count_and_pages()
            off_x_delta, off_y_delta, pdx_delta, pdy_delta = self._calibration_delta()
            off_x, off_y, pdx, pdy = self._calibration()
            self.lbl_status.configure(
                text=(
                    f"Beispiel: {text}  | {count} Labels ≈ {pages} Seiten"
                    f"  | Eingabe Offset({off_x_delta},{off_y_delta})mm PitchΔ({pdx_delta},{pdy_delta})mm"
                    f"  | Effektiv Offset({off_x},{off_y})mm PitchΔ({pdx},{pdy})mm"
                )
            )
        except Exception as e:
            self.preview.configure(image="")
            self.lbl_status.configure(text=f"⚠️ {e}")

    def _render_preview_image(self, text: str, kind: BarcodeKind, border: bool) -> Image.Image:
        scale = 6
        w = int((AVERY_L4731.label_w / mm) * scale * 10)
        h = int((AVERY_L4731.label_h / mm) * scale * 10)
        img = Image.new("RGB", (w, h), "white")

        if kind == "QR":
            size = int(h * 0.90)
            qr = make_qr_image(text, max(120, size))
            img.paste(qr, (10, (h - qr.size[1]) // 2))
        else:
            box = Image.new("RGB", (int(h * 0.90), int(h * 0.90)), "white")
            img.paste(box, (10, (h - box.size[1]) // 2))

        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 18)
        except Exception:
            font = ImageFont.load_default()
        draw.text((int(h * 0.95), (h - 18) // 2), text, fill="black", font=font)

        if border:
            draw.rectangle([0, 0, w - 1, h - 1], outline="black", width=2)

        return img.resize((360, 160), Image.Resampling.LANCZOS)

    def on_generate_pdf(self) -> None:
        try:
            start = self._parse_int(self.var_start.get(), "Start-Nummer")
            zeros = self._parse_int(self.var_zeros.get(), "Führende Nullen")
            prefix = self.var_prefix.get().strip()
            if not prefix:
                raise ValueError("Prefix darf nicht leer sein.")

            count, _pages = self._effective_count_and_pages()
            kind: BarcodeKind = "QR" if self.var_kind.get() == "QR" else "CODE128"
            off_x, off_y, pdx, pdy = self._calibration()

            default_name = f"asn_labels_{start}_{count}.pdf"
            out = filedialog.asksaveasfilename(
                title="PDF speichern",
                defaultextension=".pdf",
                initialfile=default_name,
                filetypes=[("PDF", "*.pdf")],
            )
            if not out:
                return

            pages_generated, next_number = generate_pdf(
                output_path=out,
                start_number=start,
                count=count,
                prefix=prefix,
                leading_zeros=zeros,
                kind=kind,
                layout=AVERY_L4731,
                draw_border=self.var_border.get(),
                offset_x_mm=off_x,
                offset_y_mm=off_y,
                pitch_dx_mm=pdx,
                pitch_dy_mm=pdy,
            )

            self.lbl_status.configure(
                text=f"✅ PDF: {out}  | Seiten: {pages_generated}  | Labels: {count}  | Nächster Start: {next_number}"
            )
            self.var_start.set(str(next_number))
            self._update_preview()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def on_open_folder(self) -> None:
        folder = os.getcwd()
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif os.name == "posix":
                cmd = "open" if sys.platform == "darwin" else "xdg-open"
                os.system(f'{cmd} "{folder}"')
        except Exception:
            messagebox.showinfo("Info", f"Ordner: {folder}")

    def on_reset_config(self) -> None:
        # Nachfrage, damit niemand aus Versehen alles wegklickt
        if not messagebox.askyesno(
            "Einstellungen zurücksetzen",
            "Gespeicherte Einstellungen (config.json) löschen und auf Standardwerte zurücksetzen?"
        ):
            return

        path = self._config_path()

        # 1) config.json löschen (wenn vorhanden)
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte config nicht löschen:\n{path}\n\n{e}")
            return

        # 2) Defaults anwenden (ohne Autosave-Trigger-Chaos)
        self._apply_settings_from_dict(DEFAULT_SETTINGS)

        # UI/Preview aktualisieren
        self._apply_mode()
        self._update_preview()

        # 3) Optional: Defaults direkt wieder speichern (damit nächster Start garantiert Default hat)
        self._save_settings_now()

        messagebox.showinfo("OK", f"Zurückgesetzt.\n\nConfig-Pfad:\n{path}")

def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    App(root)
    root.minsize(900, 430)
    root.mainloop()


if __name__ == "__main__":
    main()
