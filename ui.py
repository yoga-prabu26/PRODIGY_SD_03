"""
ui.py — ContactVault UI (v2 — fully polished)

Fixes applied:
  P1  ContactFormDialog: scrollable body + fixed sticky footer, 82% screen height
  P2  Toolbar buttons: explicit text_color for light/dark, border_color, hover
  P3  SearchBar: icon label + focus-glow via border_color binding
  P4  ContactDetailPanel: complete field grid with icons, typography, updated date
  P5  Category badges: emoji + label, consistent sizing
  P6  Responsiveness: minsize, wraplength via bind, no overflow
  P7  Polish: uniform spacing tokens, hover on rows, consistent typography
"""

import os
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, StringVar, IntVar
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from models import Contact, Category
from contact_manager import ContactManager

# ═══════════════════════════════════════════════════════════════════
# DESIGN TOKENS
# ═══════════════════════════════════════════════════════════════════

# Spacing
PAD_SM  = 6
PAD_MD  = 12
PAD_LG  = 20
PAD_XL  = 28

# Typography
FONT_XS   = ("Segoe UI", 9)
FONT_SM   = ("Segoe UI", 10)
FONT_MD   = ("Segoe UI", 11)
FONT_BASE = ("Segoe UI", 12)
FONT_LG   = ("Segoe UI", 13)
FONT_XL   = ("Segoe UI", 14, "bold")
FONT_2XL  = ("Segoe UI", 16, "bold")
FONT_3XL  = ("Segoe UI", 20, "bold")
FONT_STAT = ("Segoe UI", 28, "bold")

FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_MONO  = ("Consolas", 11)

# Category config: (text_color, bg_alpha_hex, emoji)
CATEGORY_CFG = {
    "Family":   ("#BF616A", "33", "🟣"),
    "Friends":  ("#5E81AC", "33", "🔵"),
    "Business": ("#2A6EBB", "33", "🟢"),
    "Personal": ("#2A7A3B", "33", "🟠"),
}

AVATAR_COLORS = [
    "#2F81F7", "#238636", "#9B59B6", "#E67E22",
    "#E74C3C", "#16A085", "#8250DF", "#F0883E",
]

MUTED = "#8B949E"
DANGER_COLOR   = "#DA3633"
DANGER_HOVER   = "#B32420"
SUCCESS_COLOR  = "#238636"
INFO_COLOR     = "#1F6FEB"
FAV_COLOR      = "#8250DF"
STAR_COLOR     = "#F0A500"
DIVIDER_COLOR  = ("#D0D7DE", "#30363D")   # light, dark tuple for CTkFrame


def _avatar_color(name: str) -> str:
    return AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]


def make_avatar_image(initials: str, name: str, size: int = 80) -> ctk.CTkImage:
    color = _avatar_color(name)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size, size], fill=color)
    fs = max(size // 3, 10)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2 - 2),
              initials, fill="white", font=font)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


# ═══════════════════════════════════════════════════════════════════
# REUSABLE COMPONENTS
# ═══════════════════════════════════════════════════════════════════

class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label, value, color, **kwargs):
        super().__init__(parent, corner_radius=12, **kwargs)
        ctk.CTkLabel(self, text=str(value), font=FONT_STAT,
                     text_color=color).pack(pady=(14, 2))
        ctk.CTkLabel(self, text=label, font=FONT_MD,
                     text_color=MUTED).pack(pady=(0, 14))


class TagPill(ctk.CTkFrame):
    def __init__(self, parent, text, color="#2F81F7", **kwargs):
        super().__init__(parent, corner_radius=20,
                         fg_color=color + "33", **kwargs)
        ctk.CTkLabel(self, text=text, font=FONT_XS,
                     text_color=color).pack(padx=8, pady=2)


class SectionLabel(ctk.CTkLabel):
    """Muted uppercase section header — matches GitHub/Linear aesthetic."""
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, text=text.upper(),
                         font=("Segoe UI", 9, "bold"),
                         text_color=MUTED, **kwargs)


class Divider(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=1,
                         fg_color=DIVIDER_COLOR, **kwargs)


class FieldRow(ctk.CTkFrame):
    """Icon + label + value row for the detail panel."""
    def __init__(self, parent, icon: str, label: str, value: str,
                 wrap: int = 220, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        # Icon column
        ctk.CTkLabel(self, text=icon, font=("Segoe UI", 13),
                     width=26, anchor="center").pack(side="left", padx=(0, 6))
        # Label column
        ctk.CTkLabel(self, text=label, font=FONT_LABEL,
                     text_color=MUTED, width=82, anchor="w").pack(side="left")
        # Value column
        ctk.CTkLabel(self, text=value, font=FONT_BASE,
                     anchor="w", wraplength=wrap,
                     justify="left").pack(side="left", fill="x", expand=True)


# ── P3: Premium search bar with icon + focus glow ─────────────────
class SearchBar(ctk.CTkFrame):
    def __init__(self, parent, on_search, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.columnconfigure(1, weight=1)

        # Search icon label
        ctk.CTkLabel(self, text="🔍", font=("Segoe UI", 14),
                     width=30).grid(row=0, column=0, padx=(8, 0))

        self._var = StringVar()
        self._var.trace_add("write", lambda *_: on_search(self._var.get()))

        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            placeholder_text="Search contacts by name, phone, email, company…",
            height=36,
            corner_radius=18,
            border_width=2,
            font=FONT_BASE,
        )
        self._entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Focus glow: change border color on focus/blur
        self._entry.bind("<FocusIn>",  self._on_focus)
        self._entry.bind("<FocusOut>", self._on_blur)

    def _on_focus(self, _=None):
        self._entry.configure(border_color="#2F81F7")

    def _on_blur(self, _=None):
        self._entry.configure(border_color=("gray70", "gray35"))

    def get(self):   return self._var.get()
    def clear(self): self._var.set("")
    def focus(self): self._entry.focus_set()


# ═══════════════════════════════════════════════════════════════════
# P1: CONTACT FORM DIALOG — fixed footer, scrollable body
# ═══════════════════════════════════════════════════════════════════

class ContactFormDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ContactManager,
                 contact: Contact = None, on_save=None):
        super().__init__(parent)
        self.manager = manager
        self.contact = contact
        self.on_save = on_save
        self.is_edit = contact is not None

        # ── dynamic sizing: 82% of screen height, max 740 ─────────
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 520, min(int(sh * 0.82), 740)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(460, 520)
        self.resizable(True, True)
        self.grab_set()

        title = "Edit Contact" if self.is_edit else "Add New Contact"
        self.title(title)

        self._build(title)
        if self.is_edit:
            self._populate()

    def _build(self, title: str):
        # ── outer layout: header / body(scrollable) / footer(fixed)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header (fixed, 56px)
        hdr = ctk.CTkFrame(self, corner_radius=0, height=56)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text=title, font=FONT_2XL).pack(
            side="left", padx=PAD_LG, pady=PAD_MD)

        # Scrollable body (expands)
        body = ctk.CTkScrollableFrame(self, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        body.columnconfigure(0, weight=1)
        self._body = body

        # ── field factory ─────────────────────────────────────────
        def field(label, placeholder, required=False, row_idx=0):
            lbl_text = f"{label}{'  *' if required else ''}"
            ctk.CTkLabel(body, text=lbl_text, font=FONT_MD,
                         anchor="w").grid(row=row_idx * 2, column=0,
                                          sticky="ew", padx=PAD_LG,
                                          pady=(PAD_MD, 0))
            e = ctk.CTkEntry(body, placeholder_text=placeholder,
                             height=36, corner_radius=8)
            e.grid(row=row_idx * 2 + 1, column=0, sticky="ew",
                   padx=PAD_LG, pady=(2, 0))
            return e

        self.f_name    = field("Full Name",     "e.g. Arjun Sharma",          True,  0)
        self.f_mobile  = field("Mobile Number", "+91 98765 43210",             True,  1)
        self.f_email   = field("Email Address", "arjun@example.com",           False, 2)
        self.f_company = field("Company",       "Organisation name",            False, 3)
        self.f_job     = field("Job Title",     "Software Engineer",            False, 4)
        self.f_address = field("Address",       "City, State, Country",         False, 5)
        self.f_tags    = field("Tags",          "python, iitm, gym  (comma-separated)", False, 6)

        # Category
        ctk.CTkLabel(body, text="Category", font=FONT_MD,
                     anchor="w").grid(row=14, column=0, sticky="ew",
                                      padx=PAD_LG, pady=(PAD_MD, 0))
        self.f_category = ctk.CTkOptionMenu(
            body, values=Category.values(), height=36, corner_radius=8)
        self.f_category.grid(row=15, column=0, sticky="ew",
                             padx=PAD_LG, pady=(2, 0))

        # Favourite checkbox
        self.f_fav = IntVar(value=0)
        ctk.CTkCheckBox(body, text="Mark as Favourite  ⭐",
                        variable=self.f_fav,
                        font=FONT_MD).grid(row=16, column=0, sticky="w",
                                           padx=PAD_LG, pady=(PAD_MD, 0))

        # Notes
        ctk.CTkLabel(body, text="Notes", font=FONT_MD,
                     anchor="w").grid(row=17, column=0, sticky="ew",
                                      padx=PAD_LG, pady=(PAD_MD, 0))
        self.f_notes = ctk.CTkTextbox(body, height=90, corner_radius=8)
        self.f_notes.grid(row=18, column=0, sticky="ew",
                          padx=PAD_LG, pady=(2, PAD_LG))

        # ── P1: FIXED sticky footer ────────────────────────────────
        footer = ctk.CTkFrame(self, corner_radius=0, height=60)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        footer.columnconfigure(0, weight=1)

        Divider(footer).place(x=0, y=0, relwidth=1)

        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(side="right", padx=PAD_LG, pady=PAD_MD)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=34,
            corner_radius=8, font=FONT_MD,
            fg_color="transparent", border_width=1,
            text_color=("gray20", "gray90"),
            border_color=("gray60", "gray40"),
            hover_color=("gray85", "#262C36"),
            command=self.destroy
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="💾  Save Contact", width=150, height=34,
            corner_radius=8, font=("Segoe UI", 11, "bold"),
            command=self._save
        ).pack(side="left")

    def _populate(self):
        c = self.contact
        def _set(w, v):
            w.delete(0, "end")
            w.insert(0, v)
        _set(self.f_name,    c.full_name)
        _set(self.f_mobile,  c.mobile)
        _set(self.f_email,   c.email)
        _set(self.f_company, c.company)
        _set(self.f_job,     c.job_title)
        _set(self.f_address, c.address)
        _set(self.f_tags,    c.tags)
        self.f_category.set(c.category.value)
        self.f_fav.set(int(c.is_favorite))
        self.f_notes.insert("1.0", c.notes)

    def _save(self):
        data = Contact(
            id=self.contact.id if self.is_edit else None,
            full_name=self.f_name.get().strip(),
            mobile=self.f_mobile.get().strip(),
            email=self.f_email.get().strip(),
            company=self.f_company.get().strip(),
            job_title=self.f_job.get().strip(),
            address=self.f_address.get().strip(),
            tags=self.f_tags.get().strip(),
            category=Category.from_str(self.f_category.get()),
            is_favorite=bool(self.f_fav.get()),
            notes=self.f_notes.get("1.0", "end").strip(),
            avatar_path=self.contact.avatar_path if self.is_edit else "",
        )
        result, payload = (self.manager.update_contact(data)
                           if self.is_edit else self.manager.add_contact(data))

        if result is True:
            if self.on_save:
                self.on_save()
            self.destroy()
        elif result == "duplicate":
            names = ", ".join(d.full_name for d in payload)
            if messagebox.askyesno(
                "Duplicate Detected",
                f"A similar contact already exists:\n{names}\n\nSave anyway?",
                parent=self
            ):
                (self.manager.db.add_contact(data)
                 if not self.is_edit else self.manager.db.update_contact(data))
                if self.on_save:
                    self.on_save()
                self.destroy()
        else:
            messagebox.showerror("Validation Error",
                                 "\n".join(payload), parent=self)


# ═══════════════════════════════════════════════════════════════════
# P4: CONTACT DETAIL PANEL — complete, rich, professional
# ═══════════════════════════════════════════════════════════════════

class ContactDetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, manager: ContactManager,
                 on_edit=None, on_delete=None, on_refresh=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.manager    = manager
        self.on_edit    = on_edit
        self.on_delete  = on_delete
        self.on_refresh = on_refresh
        self._contact   = None
        self._build_empty()

    def _build_empty(self):
        for w in self.winfo_children():
            w.destroy()
        self._contact = None
        ctk.CTkLabel(self, text="👤",
                     font=("Segoe UI", 52)).pack(pady=(80, 8))
        ctk.CTkLabel(self, text="Select a contact",
                     font=FONT_2XL).pack()
        ctk.CTkLabel(self, text="Click any name in the list to see full details.",
                     font=FONT_MD, text_color=MUTED,
                     wraplength=280).pack(pady=(4, 0))

    def load(self, contact: Contact):
        self._contact = contact
        for w in self.winfo_children():
            w.destroy()

        # ── Avatar ────────────────────────────────────────────────
        av = make_avatar_image(contact.initials(), contact.full_name, 88)
        ctk.CTkLabel(self, image=av, text="").pack(pady=(28, 6))

        # ── Name + subtitle ───────────────────────────────────────
        ctk.CTkLabel(self, text=contact.display_name(),
                     font=FONT_3XL).pack()

        subtitle = " · ".join(filter(None, [contact.job_title, contact.company]))
        if subtitle:
            ctk.CTkLabel(self, text=subtitle, font=FONT_LG,
                         text_color=MUTED).pack(pady=(2, 0))

        # ── P5: Category badge with emoji + text ──────────────────
        cat = contact.category.value
        cfg = CATEGORY_CFG.get(cat, ("#2F81F7", "33", "●"))
        badge_frame = ctk.CTkFrame(self, fg_color="transparent")
        badge_frame.pack(pady=(8, 2))
        ctk.CTkLabel(
            badge_frame,
            text=f"{cfg[2]}  {cat}",
            font=("Segoe UI", 11, "bold"),
            text_color=cfg[0],
            fg_color=cfg[0] + cfg[1],
            corner_radius=14,
            padx=14, pady=4
        ).pack()

        if contact.is_favorite:
            ctk.CTkLabel(self, text="⭐  Favourite",
                         font=FONT_MD, text_color=STAR_COLOR).pack(pady=2)

        # ── Quick-action bar ──────────────────────────────────────
        act = ctk.CTkFrame(self, fg_color="transparent")
        act.pack(pady=(10, 6))

        def quick_call():
            if contact.mobile:
                webbrowser.open(f"tel:{contact.mobile}")

        def quick_email():
            if contact.email:
                webbrowser.open(f"mailto:{contact.email}")

        def toggle_fav():
            self.manager.toggle_favorite(contact.id)
            fresh = self.manager.get_contact(contact.id)
            self.load(fresh)
            if self.on_refresh:
                self.on_refresh()

        _b = dict(height=32, corner_radius=8, font=("Segoe UI", 11, "bold"))
        ctk.CTkButton(act, text="📞  Call",  width=84,
                      fg_color=SUCCESS_COLOR, hover_color="#1a6b28",
                      **_b, command=quick_call).pack(side="left", padx=3)
        ctk.CTkButton(act, text="✉  Email", width=84,
                      fg_color=INFO_COLOR,    hover_color="#1558b0",
                      **_b, command=quick_email).pack(side="left", padx=3)
        fav_txt = "☆  Unfav" if contact.is_favorite else "★  Fav"
        ctk.CTkButton(act, text=fav_txt, width=84,
                      fg_color=FAV_COLOR,     hover_color="#6a3ab8",
                      **_b, command=toggle_fav).pack(side="left", padx=3)

        Divider(self).pack(fill="x", padx=PAD_LG, pady=(10, 14))

        # ── Contact details section ────────────────────────────────
        SectionLabel(self, "Contact Information").pack(
            anchor="w", padx=PAD_LG, pady=(0, 8))

        def detail(icon, lbl, val):
            if not (val or "").strip():
                return
            FieldRow(self, icon, lbl, val, wrap=230).pack(
                fill="x", padx=PAD_LG, pady=4)

        detail("📱", "Mobile",    contact.mobile)
        detail("📧", "Email",     contact.email)
        detail("🏢", "Company",   contact.company)
        detail("💼", "Job Title", contact.job_title)
        detail("📍", "Address",   contact.address)

        Divider(self).pack(fill="x", padx=PAD_LG, pady=(10, 14))

        # ── Metadata section ──────────────────────────────────────
        SectionLabel(self, "Record Info").pack(
            anchor="w", padx=PAD_LG, pady=(0, 8))
        detail("📅", "Created",
               contact.created_at.strftime("%d %b %Y, %H:%M")
               if contact.created_at else "")
        detail("🔄", "Updated",
               contact.updated_at.strftime("%d %b %Y, %H:%M")
               if contact.updated_at else "")
        detail("🏷", "Category",  contact.category.value)

        # ── Tags ──────────────────────────────────────────────────
        if contact.tag_list():
            Divider(self).pack(fill="x", padx=PAD_LG, pady=(10, 14))
            SectionLabel(self, "Tags").pack(anchor="w", padx=PAD_LG,
                                             pady=(0, 8))
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=PAD_LG, pady=(0, 4))
            for tag in contact.tag_list():
                TagPill(row, tag).pack(side="left", padx=2, pady=2)

        # ── Notes ─────────────────────────────────────────────────
        if contact.notes.strip():
            Divider(self).pack(fill="x", padx=PAD_LG, pady=(10, 14))
            SectionLabel(self, "Notes").pack(anchor="w", padx=PAD_LG,
                                              pady=(0, 6))
            nb = ctk.CTkTextbox(self, height=100, corner_radius=8,
                                font=FONT_BASE)
            nb.pack(fill="x", padx=PAD_LG)
            nb.insert("1.0", contact.notes)
            nb.configure(state="disabled")

        Divider(self).pack(fill="x", padx=PAD_LG, pady=(14, 10))

        # ── Edit / Delete ─────────────────────────────────────────
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.pack(pady=(0, PAD_LG))
        ctk.CTkButton(
            action_bar, text="✏  Edit Contact", width=130, height=34,
            corner_radius=8, font=FONT_MD,
            command=lambda: self.on_edit and self.on_edit(contact)
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            action_bar, text="🗑  Delete", width=100, height=34,
            corner_radius=8, font=FONT_MD,
            fg_color=DANGER_COLOR, hover_color=DANGER_HOVER,
            command=lambda: self._confirm_delete(contact)
        ).pack(side="left", padx=5)

    def _confirm_delete(self, contact: Contact):
        if messagebox.askyesno(
            "Delete Contact",
            f"Permanently delete '{contact.full_name}'?\nThis action cannot be undone."
        ):
            self.manager.delete_contact(contact.id, contact.full_name)
            if self.on_delete:
                self.on_delete()
            self._build_empty()


# ═══════════════════════════════════════════════════════════════════
# P5: CONTACT ROW — improved category badge + hover
# ═══════════════════════════════════════════════════════════════════

class ContactRow(ctk.CTkFrame):
    _SEL_COLOR   = ("gray82", "#21262D")
    _HOVER_COLOR = ("gray88", "#1C2128")

    def __init__(self, parent, contact: Contact, on_click, **kwargs):
        super().__init__(parent, corner_radius=8, cursor="hand2", **kwargs)
        self.contact    = contact
        self.on_click   = on_click
        self._selected  = False
        self._build()

        # Bind click on self and all immediate children
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>",    self._hover_on)
        self.bind("<Leave>",    self._hover_off)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._click)
            child.bind("<Enter>",    self._hover_on)
            child.bind("<Leave>",    self._hover_off)

    def _build(self):
        # Avatar (40px)
        av = make_avatar_image(self.contact.initials(),
                               self.contact.full_name, 40)
        ctk.CTkLabel(self, image=av, text="", width=48).pack(
            side="left", padx=(10, 6), pady=9)

        # Text block
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=7)

        # Name row
        nr = ctk.CTkFrame(info, fg_color="transparent")
        nr.pack(fill="x")
        ctk.CTkLabel(nr, text=self.contact.display_name(),
                     font=("Segoe UI", 13, "bold"), anchor="w").pack(side="left")
        if self.contact.is_favorite:
            ctk.CTkLabel(nr, text=" ⭐",
                         font=("Segoe UI", 10)).pack(side="left")

        # Subtitle: prefer company, fall back to mobile
        sub = self.contact.company or self.contact.mobile
        ctk.CTkLabel(info, text=sub, font=FONT_MD,
                     text_color=MUTED, anchor="w").pack(fill="x")

        # P5: Category badge with emoji + text
        cat = self.contact.category.value
        cfg = CATEGORY_CFG.get(cat, ("#2F81F7", "33", "●"))
        ctk.CTkLabel(
            self,
            text=f"{cfg[2]}  {cat}",
            font=("Segoe UI", 9, "bold"),
            text_color=cfg[0],
            fg_color=cfg[0] ,
            corner_radius=10,
            padx=8, pady=3,
            width=80
        ).pack(side="right", padx=10)

    def _click(self, _=None):
        if self.on_click:
            self.on_click(self.contact)

    def _hover_on(self, _=None):
        if not self._selected:
            self.configure(fg_color=self._HOVER_COLOR)

    def _hover_off(self, _=None):
        if not self._selected:
            self.configure(fg_color="transparent")

    def set_selected(self, val: bool):
        self._selected = val
        self.configure(fg_color=self._SEL_COLOR if val else "transparent")


# ═══════════════════════════════════════════════════════════════════
# ANALYTICS PANEL
# ═══════════════════════════════════════════════════════════════════

class AnalyticsPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, manager: ContactManager, **kwargs):
        super().__init__(parent, **kwargs)
        self.manager = manager
        self.refresh()

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()
        stats = self.manager.get_stats()

        ctk.CTkLabel(self, text="Contact Overview",
                     font=FONT_2XL).pack(anchor="w", pady=(PAD_MD, PAD_LG))

        # Stat cards grid
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=PAD_MD)
        grid.columnconfigure((0, 1), weight=1)

        cards = [
            ("Total Contacts",  stats.total,     "#2F81F7"),
            ("Business",        stats.business,  "#2A6EBB"),
            ("Family",          stats.family,    "#BF616A"),
            ("Friends",         stats.friends,   "#5E81AC"),
            ("Personal",        stats.personal,  "#2A7A3B"),
            ("Favourites ⭐",   stats.favorites, STAR_COLOR),
            ("Added This Week", stats.recent,    "#3FB950"),
        ]
        for i, (lbl, val, col) in enumerate(cards):
            StatCard(grid, lbl, val, col).grid(
                row=i // 2, column=i % 2,
                padx=PAD_SM, pady=PAD_SM, sticky="ew")

        Divider(self).pack(fill="x", pady=PAD_LG)

        # Category breakdown
        ctk.CTkLabel(self, text="Category Breakdown",
                     font=FONT_XL).pack(anchor="w", pady=(0, PAD_SM))
        cats = [
            ("Family",   stats.family,   "#BF616A"),
            ("Friends",  stats.friends,  "#5E81AC"),
            ("Business", stats.business, "#2A6EBB"),
            ("Personal", stats.personal, "#2A7A3B"),
        ]
        total = max(stats.total, 1)
        for name, count, color in cats:
            pct = count / total
            r = ctk.CTkFrame(self, fg_color="transparent")
            r.pack(fill="x", padx=PAD_MD, pady=3)
            ctk.CTkLabel(r, text=name, width=72,
                         font=FONT_MD, anchor="w").pack(side="left")
            bar_bg = ctk.CTkFrame(r, height=14, corner_radius=7)
            bar_bg.pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkFrame(bar_bg, height=14, corner_radius=7,
                         fg_color=color).place(
                relx=0, rely=0, relwidth=max(pct, 0.02), relheight=1)
            ctk.CTkLabel(r, text=f"{count}", width=28,
                         font=("Segoe UI", 11, "bold"),
                         text_color=color).pack(side="left")

        Divider(self).pack(fill="x", pady=PAD_LG)

        # Recent activity
        ctk.CTkLabel(self, text="Recent Activity",
                     font=FONT_XL).pack(anchor="w", pady=(0, PAD_SM))
        ICONS = {"added": "➕", "edited": "✏", "deleted": "🗑",
                 "imported": "📥", "exported": "📤",
                 "viewed": "👁", "favorited": "⭐"}
        logs = self.manager.get_activity_log(limit=15)
        if not logs:
            ctk.CTkLabel(self, text="No activity yet.",
                         text_color=MUTED).pack()
        for log in logs:
            r = ctk.CTkFrame(self, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=PAD_MD)
            ctk.CTkLabel(r, text=ICONS.get(log.action.value, "•"),
                         width=24).pack(side="left")
            ctk.CTkLabel(r, text=log.contact_name,
                         font=FONT_MD, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=log.timestamp.strftime("%d %b %H:%M"),
                         font=FONT_XS, text_color=MUTED).pack(side="right")


# ═══════════════════════════════════════════════════════════════════
# MAIN APPLICATION WINDOW
# ═══════════════════════════════════════════════════════════════════

class App(ctk.CTk):

    NAV_ITEMS = [
        ("All Contacts", "👥"),
        ("Favourites",   "⭐"),
        ("Family",       "🏠"),
        ("Friends",      "😊"),
        ("Business",     "💼"),
        ("Personal",     "🙋"),
        ("Analytics",    "📊"),
        ("Activity Log", "🕐"),
    ]

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("ContactVault — Contact Management System")
        self.geometry("1280x800")
        self.minsize(1060, 640)          # P6: responsive floor

        self.manager = ContactManager()
        self._theme  = "dark"
        self._current_contacts = []
        self._selected_row     = None
        self._nav_btns         = []

        self._setup_keyboard_shortcuts()
        self._build_layout()
        self._navigate("All Contacts")
        self._update_status("Ready  ·  ContactVault v2.0")

    # ── shortcuts ─────────────────────────────────────────────────
    def _setup_keyboard_shortcuts(self):
        self.bind("<Control-n>", lambda _: self._open_add_dialog())
        self.bind("<Control-f>", lambda _: self.search_bar.focus())
        self.bind("<Control-e>", lambda _: self._export_csv())
        self.bind("<Control-t>", lambda _: self._toggle_theme())
        self.bind("<Delete>",    lambda _: self._delete_selected())
        self.bind("<F5>",        lambda _: self._refresh())

    # ── layout ────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._build_titlebar()
        self._build_sidebar()
        self._build_main_area()
        self._build_statusbar()

    # ── P2: Titlebar — buttons visible in both themes ─────────────
    def _build_titlebar(self):
        bar = ctk.CTkFrame(self, height=56, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure(1, weight=1)

        # Logo
        ctk.CTkLabel(bar, text="🗂  ContactVault",
                     font=FONT_2XL).grid(row=0, column=0, padx=PAD_LG,
                                         pady=PAD_MD, sticky="w")

        # P3: Search bar
        self.search_bar = SearchBar(bar, self._on_search)
        self.search_bar.grid(row=0, column=1, padx=PAD_LG,
                             sticky="ew", pady=10)

        # Action buttons — P2: explicit colors for both themes
        acts = ctk.CTkFrame(bar, fg_color="transparent")
        acts.grid(row=0, column=2, padx=PAD_MD, pady=PAD_SM)

        # Primary: Add Contact
        ctk.CTkButton(
            acts, text="➕  Add", width=110, height=34,
            corner_radius=8, font=("Segoe UI", 11, "bold"),
            command=self._open_add_dialog
        ).pack(side="left", padx=3)

        # Secondary ghost buttons — must be visible light AND dark
        _ghost = dict(
            height=34, corner_radius=8, font=FONT_MD,
            fg_color="transparent",
            border_width=1,
            text_color=("gray15", "gray92"),       # dark text in light, light in dark
            border_color=("gray55", "gray45"),
            hover_color=("gray85", "#262C36"),
        )
        ctk.CTkButton(acts, text="📥  Import", width=94,
                      command=self._import_csv, **_ghost
                      ).pack(side="left", padx=3)
        ctk.CTkButton(acts, text="📤  Export", width=94,
                      command=self._export_menu, **_ghost
                      ).pack(side="left", padx=3)

        # Theme toggle
        self._theme_btn = ctk.CTkButton(
            acts, text="☀", width=36, height=34,
            corner_radius=8, font=("Segoe UI", 13),
            fg_color="transparent", border_width=1,
            text_color=("gray15", "gray92"),
            border_color=("gray55", "gray45"),
            hover_color=("gray85", "#262C36"),
            command=self._toggle_theme
        )
        self._theme_btn.pack(side="left", padx=3)

    # ── Sidebar ───────────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=210, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        SectionLabel(self.sidebar, "Navigation").pack(
            anchor="w", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        for label, icon in self.NAV_ITEMS:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                height=36, corner_radius=8,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray82", "#21262D"),
                font=("Segoe UI", 12),
                command=lambda l=label: self._navigate(l)
            )
            btn.pack(fill="x", padx=PAD_SM, pady=2)
            self._nav_btns.append((label, btn))

        Divider(self.sidebar).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        SectionLabel(self.sidebar, "Data").pack(
            anchor="w", padx=PAD_LG, pady=(0, PAD_SM))

        _side_btn = dict(
            anchor="w", height=34, corner_radius=8,
            fg_color="transparent",
            hover_color=("gray82", "#21262D"),
            font=("Segoe UI", 11),
        )
        ctk.CTkButton(self.sidebar, text="  💾  Backup DB",
                      command=self._backup, **_side_btn
                      ).pack(fill="x", padx=PAD_SM, pady=2)
        ctk.CTkButton(self.sidebar, text="  📂  Restore DB",
                      command=self._restore, **_side_btn
                      ).pack(fill="x", padx=PAD_SM, pady=2)

    # ── Main area ─────────────────────────────────────────────────
    def _build_main_area(self):
        self.main = ctk.CTkFrame(self, corner_radius=0)
        self.main.grid(row=1, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        # Subheader bar
        sub = ctk.CTkFrame(self.main, height=44, corner_radius=0)
        sub.grid(row=0, column=0, columnspan=2, sticky="ew")
        sub.grid_propagate(False)
        sub.columnconfigure(0, weight=1)
        self.subheader = sub

        self.page_title = ctk.CTkLabel(
            sub, text="All Contacts", font=FONT_XL, anchor="w")
        self.page_title.grid(row=0, column=0, padx=PAD_LG, pady=10, sticky="w")

        sort_frame = ctk.CTkFrame(sub, fg_color="transparent")
        sort_frame.grid(row=0, column=1, padx=PAD_MD)
        ctk.CTkLabel(sort_frame, text="Sort:", font=FONT_MD
                     ).pack(side="left", padx=(0, 4))
        self.sort_var  = StringVar(value="Name")
        self.sort_menu = ctk.CTkOptionMenu(
            sort_frame,
            values=["Name", "Company", "Date Added", "Category"],
            variable=self.sort_var,
            width=130, height=28,
            command=lambda _: self._refresh()
        )
        self.sort_menu.pack(side="left")

        # P6: contact list fixed width, detail panel expands
        self.contact_list_frame = ctk.CTkScrollableFrame(
            self.main, width=370)
        self.contact_list_frame.grid(row=1, column=0, sticky="nsew")

        self.detail_panel = ContactDetailPanel(
            self.main, manager=self.manager,
            on_edit=self._open_edit_dialog,
            on_delete=self._refresh,
            on_refresh=self._refresh,
            width=400,
        )
        self.detail_panel.grid(row=1, column=1, sticky="nsew")
        self.main.grid_columnconfigure(1, weight=1)

        self.analytics_panel = AnalyticsPanel(self.main, self.manager)
        self.activity_frame  = ctk.CTkScrollableFrame(self.main)

    # ── Status bar ────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=26, corner_radius=0)
        bar.grid(row=2, column=0, columnspan=3, sticky="ew")
        bar.grid_propagate(False)

        self._status_lbl = ctk.CTkLabel(bar, text="", font=FONT_XS,
                                         text_color=MUTED)
        self._status_lbl.pack(side="left", padx=PAD_LG)

        ctk.CTkLabel(
            bar,
            text="Ctrl+N: Add  |  Ctrl+F: Search  |  Ctrl+E: Export  |  Ctrl+T: Theme  |  F5: Refresh",
            font=FONT_XS, text_color=MUTED
        ).pack(side="right", padx=PAD_XL)

        self._count_lbl = ctk.CTkLabel(bar, text="", font=FONT_XS,
                                        text_color=MUTED)
        self._count_lbl.pack(side="right", padx=PAD_LG)

    # ── Navigation ────────────────────────────────────────────────
    def _navigate(self, section: str):
        self.search_bar.clear()
        self.page_title.configure(text=section)

        # Highlight active nav button
        active_color = ("gray82", "#21262D")
        for lbl, btn in self._nav_btns:
            btn.configure(fg_color=active_color if lbl == section else "transparent")

        # Hide all content panels
        for p in [self.contact_list_frame, self.detail_panel,
                  self.analytics_panel, self.activity_frame]:
            p.grid_remove()

        self.sort_menu.master.grid()   # show sort frame by default

        if section in ("All Contacts", "Favourites",
                       "Family", "Friends", "Business", "Personal"):
            if section == "All Contacts":
                data = self.manager.get_all_contacts(*self._sort_params())
            elif section == "Favourites":
                data = self.manager.get_favorites()
            else:
                data = self.manager.filter_by_category(
                    Category.from_str(section))
            self._load_contacts(data)
            self.contact_list_frame.grid(row=1, column=0, sticky="nsew")
            self.detail_panel.grid(row=1, column=1, sticky="nsew")

        elif section == "Analytics":
            self.sort_menu.master.grid_remove()
            self.analytics_panel.refresh()
            self.analytics_panel.grid(row=1, column=0,
                                       columnspan=2, sticky="nsew")

        elif section == "Activity Log":
            self.sort_menu.master.grid_remove()
            self._build_activity_log()
            self.activity_frame.grid(row=1, column=0,
                                      columnspan=2, sticky="nsew")

        self._current_section = section

    def _sort_params(self):
        mapping = {"Name": "full_name", "Company": "company",
                   "Date Added": "created_at", "Category": "category"}
        return mapping.get(self.sort_var.get(), "full_name"), "ASC"

    # ── Contact list ──────────────────────────────────────────────
    def _load_contacts(self, contacts: list):
        self._current_contacts = contacts
        for w in self.contact_list_frame.winfo_children():
            w.destroy()
        self._selected_row = None

        if not contacts:
            ctk.CTkLabel(self.contact_list_frame,
                         text="No contacts found.",
                         font=FONT_LG, text_color=MUTED).pack(pady=60)
            self._count_lbl.configure(text="0 contacts")
            return

        for c in contacts:
            ContactRow(self.contact_list_frame, c,
                       on_click=self._on_contact_click
                       ).pack(fill="x", padx=4, pady=2)

        n = len(contacts)
        self._count_lbl.configure(
            text=f"{n} contact{'s' if n != 1 else ''}")

    def _on_contact_click(self, contact: Contact):
        for w in self.contact_list_frame.winfo_children():
            if isinstance(w, ContactRow):
                w.set_selected(w.contact.id == contact.id)
        fresh = self.manager.get_contact(contact.id)
        if fresh:
            self.detail_panel.load(fresh)

    # ── Search ────────────────────────────────────────────────────
    def _on_search(self, query: str):
        if not query.strip():
            self._navigate(getattr(self, "_current_section", "All Contacts"))
            return
        results = self.manager.search(query)
        self._load_contacts(results)
        # show both panels
        self.contact_list_frame.grid(row=1, column=0, sticky="nsew")
        self.detail_panel.grid(row=1, column=1, sticky="nsew")
        self.page_title.configure(text=f'Search: "{query}"')

    # ── Dialogs ───────────────────────────────────────────────────
    def _open_add_dialog(self):
        ContactFormDialog(self, self.manager, on_save=self._refresh)

    def _open_edit_dialog(self, contact: Contact):
        ContactFormDialog(self, self.manager, contact=contact,
                          on_save=self._refresh)

    def _delete_selected(self):
        if self.detail_panel._contact:
            self.detail_panel._confirm_delete(self.detail_panel._contact)

    # ── Import / Export ───────────────────────────────────────────
    def _import_csv(self):
        path = filedialog.askopenfilename(
            title="Import Contacts from CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        added, skipped, errors = self.manager.import_csv(path)
        msg = f"✅ Imported {added} contact(s)."
        if skipped:
            msg += f"\n⚠ {skipped} skipped (duplicates)."
        if errors:
            msg += f"\n❌ {len(errors)} error(s)."
        messagebox.showinfo("Import Complete", msg)
        self._refresh()

    def _export_csv(self):
        path = self.manager.export_csv()
        messagebox.showinfo("Export Complete", f"CSV saved to:\n{path}")

    def _export_excel(self):
        try:
            path = self.manager.export_excel()
            messagebox.showinfo("Export Complete", f"Excel saved to:\n{path}")
        except RuntimeError as e:
            messagebox.showerror("Export Error", str(e))

    def _export_menu(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Export Contacts")
        popup.geometry("300x200")
        popup.resizable(False, False)
        popup.grab_set()
        ctk.CTkLabel(popup, text="Choose Export Format",
                     font=FONT_XL).pack(pady=PAD_LG)
        ctk.CTkButton(popup, text="📄  Export as CSV (.csv)", width=220,
                      height=38, corner_radius=8,
                      command=lambda: [popup.destroy(), self._export_csv()]
                      ).pack(pady=6)
        ctk.CTkButton(popup, text="📊  Export as Excel (.xlsx)", width=220,
                      height=38, corner_radius=8,
                      command=lambda: [popup.destroy(), self._export_excel()]
                      ).pack(pady=6)

    def _backup(self):
        path = self.manager.backup()
        messagebox.showinfo("Backup Created",
                            f"Database backed up to:\n{path}")

    def _restore(self):
        path = filedialog.askopenfilename(
            title="Restore Database",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")])
        if path and messagebox.askyesno(
                "Restore Database",
                "This will REPLACE the current database.\nProceed?"):
            ok = self.manager.restore(path)
            if ok:
                messagebox.showinfo("Restore Complete",
                                    "Database restored successfully.")
                self._refresh()
            else:
                messagebox.showerror("Restore Failed",
                                     "Could not restore the selected file.")

    # ── Activity log view ─────────────────────────────────────────
    def _build_activity_log(self):
        for w in self.activity_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.activity_frame, text="Recent Activity",
                     font=FONT_2XL).pack(anchor="w", pady=(PAD_MD, PAD_LG))
        logs = self.manager.get_activity_log(100)
        if not logs:
            ctk.CTkLabel(self.activity_frame,
                         text="No activity recorded yet.",
                         text_color=MUTED).pack(pady=60)
            return
        ICONS = {"added": "➕", "edited": "✏", "deleted": "🗑",
                 "imported": "📥", "exported": "📤",
                 "viewed": "👁", "favorited": "⭐"}
        for log in logs:
            row = ctk.CTkFrame(self.activity_frame, corner_radius=8)
            row.pack(fill="x", pady=3, padx=PAD_MD)
            ctk.CTkLabel(row, text=ICONS.get(log.action.value, "•"),
                         width=32, font=("Segoe UI", 14)
                         ).pack(side="left", padx=PAD_MD, pady=PAD_MD)
            ctk.CTkLabel(row,
                         text=f"{log.action.value.title()}  —  {log.contact_name}",
                         font=FONT_BASE, anchor="w"
                         ).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row,
                         text=log.timestamp.strftime("%d %b %Y, %H:%M"),
                         font=FONT_XS, text_color=MUTED
                         ).pack(side="right", padx=PAD_MD)

    # ── Theme toggle ──────────────────────────────────────────────
    def _toggle_theme(self):
        self._theme = "light" if self._theme == "dark" else "dark"
        ctk.set_appearance_mode(self._theme)
        icon = "🌙" if self._theme == "dark" else "☀"
        self._theme_btn.configure(text=icon)
        self._update_status(f"Switched to {self._theme.title()} mode")

    # ── Helpers ───────────────────────────────────────────────────
    def _refresh(self):
        self._navigate(getattr(self, "_current_section", "All Contacts"))

    def _update_status(self, msg: str):
        self._status_lbl.configure(text=msg)


# ═══════════════════════════════════════════════════════════════════
# SEED + ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def _seed_demo_data(manager: ContactManager):
    if manager.get_stats().total > 0:
        return
    demos = [
        Contact("Arjun Sharma",    "+91 98765 43210", "arjun@example.com",
                "Chennai, Tamil Nadu",   "Infosys Ltd",     "Software Engineer",
                "College friend. Loves cricket.",
                Category.FRIENDS,  "python,cricket", True),
        Contact("Priya Nair",      "+91 87654 32109", "priya.nair@startup.io",
                "Bengaluru, Karnataka",  "Startup.io",      "Product Manager",
                "Met at NASSCOM summit.",
                Category.BUSINESS, "product,startup"),
        Contact("Ravi Kumar",      "+91 76543 21098", "ravi@gmail.com",
                "Hyderabad, Telangana",  "",                "Student",
                "IITM Pravartak cohort.",
                Category.FRIENDS,  "iitm,hackathon"),
        Contact("Ananya Krishnan", "+91 65432 10987", "ananya@family.com",
                "Coimbatore, Tamil Nadu", "",               "",
                "Elder sister.",
                Category.FAMILY,   "family", True),
        Contact("Vikram Mehta",    "+91 54321 09876", "vikram@corp.com",
                "Mumbai, Maharashtra",   "TechCorp India",  "CTO",
                "Potential investor. Follow up Q3.",
                Category.BUSINESS, "investor,fintech"),
        Contact("Deepika Pillai",  "+91 43210 98765", "deepika@design.co",
                "Pune, Maharashtra",     "Design.co",       "UI/UX Designer",
                "Collaborated on SpendSense UI.",
                Category.PERSONAL, "design,ux"),
        Contact("Suresh Iyer",     "+91 32109 87654", "suresh@family.com",
                "Madurai, Tamil Nadu",   "",                "",
                "Uncle. Calls every Sunday.",
                Category.FAMILY,   "family"),
        Contact("Kavitha Reddy",   "+91 21098 76543", "kavitha@ngo.org",
                "Vijayawada, AP",        "GreenEarth NGO",  "Volunteer Lead",
                "Environmental activist.",
                Category.PERSONAL, "ngo,sustainability"),
    ]
    for c in demos:
        manager.db.add_contact(c)


def run():
    _manager = ContactManager()
    _seed_demo_data(_manager)
    app = App()
    app.mainloop()
