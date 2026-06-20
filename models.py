"""
models.py — Data models and enumerations for ContactVault.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Category(str, Enum):
    FAMILY = "Family"
    FRIENDS = "Friends"
    BUSINESS = "Business"
    PERSONAL = "Personal"

    @classmethod
    def values(cls) -> list:
        return [c.value for c in cls]

    @classmethod
    def from_str(cls, value: str) -> "Category":
        for c in cls:
            if c.value.lower() == value.lower():
                return c
        return cls.PERSONAL


class ActivityType(str, Enum):
    ADDED = "added"
    EDITED = "edited"
    DELETED = "deleted"
    IMPORTED = "imported"
    EXPORTED = "exported"
    VIEWED = "viewed"
    FAVORITED = "favorited"


@dataclass
class Contact:
    full_name: str
    mobile: str
    email: str = ""
    address: str = ""
    company: str = ""
    job_title: str = ""
    notes: str = ""
    category: object = None
    tags: str = ""
    is_favorite: bool = False
    avatar_path: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.category is None:
            self.category = Category.PERSONAL
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if isinstance(self.category, str):
            self.category = Category.from_str(self.category)

    def validate(self) -> list:
        errors = []
        if not self.full_name.strip():
            errors.append("Full name is required.")
        if not self.mobile.strip():
            errors.append("Mobile number is required.")
        if self.email.strip() and "@" not in self.email:
            errors.append("Email address is not valid.")
        return errors

    def display_name(self) -> str:
        return self.full_name.strip() or "Unnamed Contact"

    def initials(self) -> str:
        parts = self.display_name().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return parts[0][:2].upper() if parts else "?"

    def tag_list(self) -> list:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def matches_query(self, query: str) -> bool:
        q = query.lower()
        return any(q in f.lower() for f in [
            self.full_name, self.mobile, self.email,
            self.company, self.job_title, self.address, self.tags
        ])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "mobile": self.mobile,
            "email": self.email,
            "address": self.address,
            "company": self.company,
            "job_title": self.job_title,
            "notes": self.notes,
            "category": self.category.value,
            "tags": self.tags,
            "is_favorite": int(self.is_favorite),
            "avatar_path": self.avatar_path,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


@dataclass
class ActivityLog:
    action: ActivityType
    contact_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    detail: str = ""
    id: Optional[int] = None


@dataclass
class AppStats:
    total: int = 0
    family: int = 0
    friends: int = 0
    business: int = 0
    personal: int = 0
    favorites: int = 0
    recent: int = 0
