"""Data model types for the library."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """A user record."""
    id: int
    name: str
    email: Optional[str] = None

    def display_name(self) -> str:
        return self.name


@dataclass
class Order:
    """An order record."""
    id: int
    user_id: int
    total: float

    def apply_discount(self, pct: float) -> None:
        self.total *= (1 - pct / 100)


class UserRepository:
    """In-memory user store."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}

    def get(self, user_id: int) -> Optional[User]:
        return self._users.get(user_id)

    def save(self, user: User) -> None:
        self._users[user.id] = user
