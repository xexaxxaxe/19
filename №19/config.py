"""Application settings and shared reference values."""
from pathlib import Path

APP_TITLE = "Полевой архив — учёт археологических находок"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "archive.db"

CATEGORIES = (
    "Керамика", "Монеты", "Орудия труда", "Украшения",
    "Оружие", "Предметы быта", "Скульптура", "Прочее",
)
CONDITIONS = ("Отличное", "Хорошее", "Удовлетворительное", "Требует реставрации")
LAB_STATUSES = ("Назначен", "В работе", "Завершён", "Отменён")
ACTIVE_LAB_STATUSES = ("Назначен", "В работе")
SORT_LABELS = {
    "Инвентарный номер": "code",
    "Наименование": "title",
    "Глубина (см)": "depth",
    "Возраст (лет)": "age",
    "Дата обнаружения": "date",
    "Участок": "site",
    "Хранилище": "storage",
}
