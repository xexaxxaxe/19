"""Domain-level representations and canonical identifiers."""
from dataclasses import dataclass
from typing import Optional


def normalize_inventory_code(value: str) -> str:
    """Return the canonical case-insensitive archive identifier."""
    return " ".join(str(value).strip().split()).upper()#upper


@dataclass(frozen=True)
class Finding:
    inventory_code: str
    title: str
    category: str
    site_id: int
    discovery_date: str
    depth_cm: float
    age_years: int
    material: str
    condition: str
    storage_id: int
    description: str = ""
    id: Optional[int] = None

    def as_record(self) -> dict:
        return {
            "inventory_code": self.inventory_code,
            "title": self.title,
            "category": self.category,
            "site_id": self.site_id,
            "discovery_date": self.discovery_date,
            "depth_cm": self.depth_cm,
            "age_years": self.age_years,
            "material": self.material,
            "condition": self.condition,
            "storage_id": self.storage_id,
            "description": self.description,
        }
