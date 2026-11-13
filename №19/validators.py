"""Input validation and time-period rules."""
from datetime import date
from config import CATEGORIES, CONDITIONS
from models import Finding, normalize_inventory_code


def parse_iso_date(value: str, field: str) -> str:
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{field}: укажите дату в формате ГГГГ-ММ-ДД.") from exc


def parse_nonnegative_float(value, field: str) -> float:
    try:
        result = float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{field}: требуется число.") from exc
    if not (0 <= result <= 100_000) or result != result:
        raise ValueError(f"{field}: число должно быть от 0 до 100 000.")
    return result


def parse_nonnegative_int(value, field: str) -> int:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: требуется целое число.") from exc
    if result < 0 or result > 1_000_000:
        raise ValueError(f"{field}: число должно быть от 0 до 1 000 000.")
    return result


def require_text(value, field: str, max_length: int = 180) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field}: поле обязательно для заполнения.")
    if len(result) > max_length:
        raise ValueError(f"{field}: максимум {max_length} символов.")
    return result


def validate_finding(raw: dict) -> Finding:
    code = normalize_inventory_code(require_text(raw.get("inventory_code"), "Инвентарный номер", 40))
    title = require_text(raw.get("title"), "Наименование", 150)
    category = require_text(raw.get("category"), "Категория")
    if category not in CATEGORIES:
        raise ValueError("Выберите категорию из списка.")
    condition = require_text(raw.get("condition"), "Сохранность")
    if condition not in CONDITIONS:
        raise ValueError("Выберите состояние находки из списка.")
    material = require_text(raw.get("material"), "Материал", 100)
    try:
        site_id = int(raw.get("site_id"))
        storage_id = int(raw.get("storage_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Укажите участок и хранилище.") from exc
    if site_id <= 0 or storage_id <= 0:
        raise ValueError("Укажите участок и хранилище.")
    description = str(raw.get("description") or "").strip()
    if len(description) > 3000:
        raise ValueError("Описание слишком длинное (максимум 3000 символов).")
    return Finding(
        inventory_code=code, title=title, category=category, site_id=site_id,
        discovery_date=parse_iso_date(raw.get("discovery_date", ""), "Дата обнаружения"),
        depth_cm=parse_nonnegative_float(raw.get("depth_cm"), "Глубина"),
        age_years=parse_nonnegative_int(raw.get("age_years"), "Возраст"),
        material=material, condition=condition, storage_id=storage_id,
        description=description,
    )


def periods_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """The dates of two laboratory stays are inclusive on both ends."""
    return start_a <= end_b and end_a >= start_b#<=, >=


def validate_lab_dates(start: str, end: str) -> tuple[str, str]:
    a = parse_iso_date(start, "Дата начала")
    b = parse_iso_date(end, "Дата окончания")
    if a > b:
        raise ValueError("Дата окончания не может быть раньше даты начала.")
    return a, b
