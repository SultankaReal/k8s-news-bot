from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    url: str
    title: str
    source: str
    published: Optional[datetime] = None
    summary: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def short_repr(self) -> str:
        pub = f" ({self.published.strftime('%d.%m')})" if self.published else ""
        return f"**{self.title}**{pub} — {self.source}\n{self.url}"
