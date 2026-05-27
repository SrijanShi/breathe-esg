from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedRow:
    row_number: int
    data: dict[str, Any]
    status: str = "ok"  # ok | warning | error | skipped
    errors: list[dict] = field(default_factory=list)

    def add_error(self, field_name: str, message: str):
        self.errors.append({"field": field_name, "message": message})
        self.status = "error"

    def add_warning(self, field_name: str, message: str):
        self.errors.append({"field": field_name, "message": f"[WARNING] {message}"})
        if self.status == "ok":
            self.status = "warning"


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes) -> list[ParsedRow]:
        """Parse raw file bytes, return list of ParsedRow objects."""
        ...
