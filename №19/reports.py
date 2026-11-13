"""Aggregated reporting and CSV output."""
import csv


def storage_occupancy(con):
    """Count physical items at each current storage location."""
    return [dict(r) for r in con.execute("""SELECT s.id, s.name, s.capacity, COUNT(f.id) AS quantity
      FROM storages s LEFT JOIN findings f ON f.storage_id=s.id
      GROUP BY s.id, s.name, s.capacity ORDER BY s.name COLLATE NOCASE""")]


def summary(con):
    single = lambda sql: con.execute(sql).fetchone()[0]
    by_category = [dict(r) for r in con.execute("""SELECT category AS name, COUNT(*) AS quantity
        FROM findings GROUP BY category ORDER BY quantity DESC, category""")]
    by_site = [dict(r) for r in con.execute("""SELECT s.name AS name, COUNT(f.id) AS quantity
        FROM sites s LEFT JOIN findings f ON s.id=f.site_id
        GROUP BY s.id, s.name ORDER BY quantity DESC, s.name""")]
    labs = [dict(r) for r in con.execute("""SELECT status AS name, COUNT(*) AS quantity FROM lab_requests
        GROUP BY status ORDER BY status""")]
    return {
        "total": single("SELECT COUNT(*) FROM findings"),
        "sites": single("SELECT COUNT(*) FROM sites"),
        "active_labs": single("SELECT COUNT(*) FROM lab_requests WHERE status IN ('Назначен','В работе')"),
        "average_depth": single("SELECT COALESCE(ROUND(AVG(depth_cm),1),0) FROM findings"),
        "by_category": by_category,
        "by_site": by_site,
        "by_storage": storage_occupancy(con),
        "by_lab": labs,
    }


def export_findings_csv(rows, path):
    """Write exactly the currently filtered and sorted table."""
    columns = [
        ("inventory_code", "Инвентарный номер"),
        ("title", "Наименование"),
        ("category", "Категория"),
        ("site_name", "Участок"),
        ("discovery_date", "Дата обнаружения"),
        ("depth_cm", "Глубина, см"),
        ("age_years", "Возраст, лет"),
        ("material", "Материал"),
        ("condition", "Сохранность"),
        ("storage_name", "Хранилище"),
        ("description", "Описание"),
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as out:
        writer = csv.writer(out, delimiter=";")
        writer.writerow([label for _, label in columns])
        for row in rows:
            writer.writerow([row.get(field, "") for field, _ in columns])
    return len(rows)
