from __future__ import annotations
from typing import Callable, Optional, Protocol

class JobScheduler(Protocol):
    def submit(self, fn: Callable[[], None], *, name: Optional[str] = None) -> str:
        ...