"""SQLite schema, transactions and standalone example data."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import date, timedelta


@contextmanager
def session(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    period TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS storages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 0 CHECK(capacity >= 0),
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE RESTRICT,
    discovery_date TEXT NOT NULL,
    depth_cm REAL NOT NULL CHECK(depth_cm >= 0),
    age_years INTEGER NOT NULL CHECK(age_years >= 0),
    material TEXT NOT NULL,
    condition TEXT NOT NULL,
    storage_id INTEGER NOT NULL REFERENCES storages(id) ON DELETE RESTRICT,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id) ON DELETE SET NULL,
    inventory_snapshot TEXT NOT NULL,
    from_storage_id INTEGER REFERENCES storages(id) ON DELETE SET NULL,
    to_storage_id INTEGER REFERENCES storages(id) ON DELETE SET NULL,
    from_storage_name TEXT NOT NULL,
    to_storage_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    moved_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lab_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id) ON DELETE SET NULL,
    inventory_snapshot TEXT NOT NULL,
    laboratory TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS change_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id) ON DELETE SET NULL, 
    inventory_snapshot TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_findings_site ON findings(site_id);
CREATE INDEX IF NOT EXISTS idx_findings_storage ON findings(storage_id);
CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(category);
CREATE INDEX IF NOT EXISTS idx_movements_finding ON movements(finding_id);
CREATE INDEX IF NOT EXISTS idx_labs_finding ON lab_requests(finding_id);
CREATE INDEX IF NOT EXISTS idx_change_logs_finding ON change_logs(finding_id);
"""

def _migrate_change_logs(con):
    """Old databases deleted a finding's history together with the finding (ON DELETE CASCADE)."""
    row = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='change_logs'").fetchone()
    if not row or "ON DELETE CASCADE" not in row[0]:
        return
    con.executescript("""
        ALTER TABLE change_logs RENAME TO change_logs_old;
        CREATE TABLE change_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id INTEGER REFERENCES findings(id) ON DELETE SET NULL,
            inventory_snapshot TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO change_logs(id, finding_id, inventory_snapshot, action, details, created_at)
            SELECT id, finding_id, inventory_snapshot, action, details, created_at FROM change_logs_old;
        DROP TABLE change_logs_old;
        CREATE INDEX IF NOT EXISTS idx_change_logs_finding ON change_logs(finding_id);
    """)

def initialize(db_path, seed=True):
    path = Path(db_path)
    is_new = not path.is_file() or path.stat().st_size == 0
    with session(path) as con:
        con.executescript(SCHEMA)
        if seed and is_new:
            seed_demo(con)


def seed_demo(con):
    """Plausible fictional records; none represent verified actual excavations."""
    sites = [
        ("Талгарское городище", "Алматинская область", "Средневековье", "Учебная группа A"),
        ("Иссыкский некрополь", "Алматинская область", "Ранний железный век", "Учебная группа B"),
        ("Тамгалы", "Алматинская область", "Бронзовый век", "Учебная группа C"),
        ("Койлык", "Жетысуская область", "Средневековье", "Учебная группа A"),
        ("Боралдайские курганы", "Алматы", "Ранний железный век", "Учебная группа D"),
        ("Отрар", "Туркестанская область", "Средневековье", "Учебная группа C"),
        ("Сарайшык", "Атырауская область", "Средневековье", "Учебная группа E"),
        ("Берель", "Восточно-Казахстанская область", "Ранний железный век", "Учебная группа D"),
    ]
    con.executemany("INSERT INTO sites(name, region, period, notes) VALUES(?, ?, ?, ?)", sites)
    storages = [
        ("Основной фонд", "Корпус A, помещение 101", 300, "Учетный фонд"),
        ("Керамический фонд", "Корпус A, помещение 102", 180, "Керамика и фрагменты"),
        ("Металлофонд", "Корпус B, помещение 203", 140, "Монеты и металлические изделия"),
        ("Реставрационное хранение", "Мастерская R, шкаф 4", 80, "На предварительной обработке"),
        ("Экспозиционный резерв", "Корпус C, помещение 301", 95, "Временное размещение"),
    ]
    con.executemany("INSERT INTO storages(name, location, capacity, notes) VALUES(?, ?, ?, ?)", storages)
    entries = [
        ("Фрагмент расписного кувшина", "Керамика", "Глина"),
        ("Медная монета с орнаментом", "Монеты", "Медь"),
        ("Каменный скребок", "Орудия труда", "Кремень"),
        ("Серебряная серьга", "Украшения", "Серебро"),
        ("Бронзовый наконечник стрелы", "Оружие", "Бронза"),
        ("Глиняная пряслица", "Предметы быта", "Глина"),
        ("Фрагмент терракотовой фигурки", "Скульптура", "Терракота"),
        ("Керамическая чаша", "Керамика", "Глина"),
        ("Бронзовый перстень", "Украшения", "Бронза"),
        ("Железное шило", "Орудия труда", "Железо"),
        ("Стеклянная бусина", "Украшения", "Стекло"),
        ("Серебряная монета", "Монеты", "Серебро"),
        ("Небольшая каменная ступка", "Предметы быта", "Гранит"),
        ("Фрагмент керамического сосуда", "Керамика", "Глина"),
        ("Костяная игла", "Орудия труда", "Кость"),
        ("Бронзовая пряжка", "Украшения", "Бронза"),
        ("Фрагмент глиняной статуэтки", "Скульптура", "Глина"),
        ("Железный нож", "Оружие", "Железо"),
        ("Глазурованная пиала", "Керамика", "Керамика"),
        ("Медная подвеска", "Украшения", "Медь"),
        ("Костяной гребень", "Предметы быта", "Кость"),
        ("Бронзовый топор", "Орудия труда", "Бронза"),
        ("Фрагмент орнаментальной плиты", "Прочее", "Камень"),
        ("Керамическая крышка", "Керамика", "Глина"),
        ("Железный наконечник копья", "Оружие", "Железо"),
        ("Монета с растительным мотивом", "Монеты", "Медь"),
        ("Каменная печать", "Предметы быта", "Сланец"),
        ("Бронзовая фибула", "Украшения", "Бронза"),
        ("Рельефный фрагмент", "Скульптура", "Камень"),
        ("Керамический светильник", "Предметы быта", "Глина"),
        ("Наконечник костяного гарпуна", "Орудия труда", "Кость"),
        ("Фрагмент чаши с ангобом", "Керамика", "Глина"),
        ("Серебряный браслет", "Украшения", "Серебро"),
        ("Чеканная монета", "Монеты", "Медь"),
        ("Обломок литой фигурки", "Скульптура", "Бронза"),
        ("Каменная бусина", "Украшения", "Агат"),
    ]
    for i, (title, category, material) in enumerate(entries, start=1):
        site = ((i * 3) % len(sites)) + 1
        store = ((i + 2) % len(storages)) + 1
        depth = [5, 18, 42, 9, 110, 63, 27, 135, 7, 58][(i - 1) % 10] + (i % 4) * 0.5
        age = [350, 700, 1500, 2200, 900, 1200, 1800, 600][(i - 1) % 8] + (i % 5) * 15
        discovery = date(2026, 3, 1) + timedelta(days=i * 4)
        condition = ["Хорошее", "Удовлетворительное", "Требует реставрации", "Отличное"][i % 4]
        code = f"AR-2026-{i:04d}"
        con.execute("""INSERT INTO findings
            (inventory_code,title,category,site_id,discovery_date,depth_cm,age_years,
             material,condition,storage_id,description)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (code, title, category, site, discovery.isoformat(), depth, age,
             material, condition, store, f"Учебная демонстрационная находка №{i}; сектор {chr(65 + i % 5)}."))
        con.execute("""INSERT INTO change_logs(finding_id,inventory_snapshot,action,details)
                        VALUES(?,?,'Создание',?)""", (i, code, "Импорт демонстрационной записи"))
    for finding_id, source, target in [(4, 2, 4), (9, 2, 5), (17, 5, 4), (25, 3, 1), (30, 3, 2)]:
        code = f"AR-2026-{finding_id:04d}"
        con.execute("UPDATE findings SET storage_id=? WHERE id=?", (target, finding_id))
        con.execute("""INSERT INTO movements(finding_id,inventory_snapshot,from_storage_id,to_storage_id,
            from_storage_name,to_storage_name,reason) VALUES(?,?,?,?,?,?,?)""",
            (finding_id, code, source, target, storages[source - 1][0], storages[target - 1][0], "Учебная передача фонда"))
        con.execute("""INSERT INTO change_logs(finding_id,inventory_snapshot,action,details)
                       VALUES(?,?,'Перемещение',?)""", (finding_id, code, "Учебная передача фонда"))
    for i, fid in enumerate([2, 7, 13, 18, 23, 32]):
        starts = ["2026-07-01", "2026-08-05", "2026-09-10", "2026-09-25", "2026-10-08", "2026-11-15"]
        ends = ["2026-07-09", "2026-08-15", "2026-09-17", "2026-10-01", "2026-10-16", "2026-11-25"]
        statuses = ["Завершён", "Завершён", "Завершён", "В работе", "Назначен", "Назначен"]
        con.execute("""INSERT INTO lab_requests(finding_id,inventory_snapshot,laboratory,
            start_date,end_date,status,purpose,result) VALUES(?,?,?,?,?,?,?,?)""",
            (fid, f"AR-2026-{fid:04d}", ["Лаборатория материалов", "Центр датировки", "Реставрационная лаборатория"][i % 3],
             starts[i], ends[i], statuses[i], "Анализ состава и состояния", "Образец исследован" if i < 3 else ""))
