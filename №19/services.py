"""Application use-cases, validation, and transactional consistency."""
import sqlite3
from database import session
from repository import ArchiveRepository as Repo
from reports import summary, export_findings_csv
from validators import (
    validate_finding, validate_lab_dates, periods_overlap, require_text,
    parse_nonnegative_int, parse_nonnegative_float,
)
from config import ACTIVE_LAB_STATUSES, LAB_STATUSES


class ArchiveService:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def _using(self):
        return session(self.db_path)

    def list_findings(self, filters=None, sort_by="code", descending=False):
        filters = dict(filters or {})
        for field in ("min_depth", "max_depth"):
            if filters.get(field) not in (None, ""):
                filters[field] = parse_nonnegative_float(filters[field], "Глубина")
        if (filters.get("min_depth") is not None and filters.get("min_depth") != "" and
            filters.get("max_depth") is not None and filters.get("max_depth") != "" and
            filters["min_depth"] > filters["max_depth"]):
            raise ValueError("Минимальная глубина больше максимальной.")
        with self._using() as con:
            return Repo.list_findings(con, filters, sort_by, descending)

    def list_sites(self):
        with self._using() as con:
            return Repo.list_sites(con)

    def list_storages(self):
        with self._using() as con:
            return Repo.list_storages(con)

    def get_finding(self, finding_id):
        with self._using() as con:
            return Repo.one(con, "findings", finding_id)

    def list_movements(self):
        with self._using() as con:
            return Repo.list_movements(con)

    def list_history(self):
        with self._using() as con:
            return Repo.list_history(con)

    def list_labs(self):
        with self._using() as con:
            return Repo.list_labs(con)

    def stats(self):
        with self._using() as con:
            return summary(con)

    def save_finding(self, raw, finding_id=None):
        finding = validate_finding(raw)
        rec = finding.as_record()
        with self._using() as con:
            if not Repo.one(con, "sites", finding.site_id):
                raise ValueError("Указанный участок не существует.")
            if not Repo.one(con, "storages", finding.storage_id):
                raise ValueError("Указанное хранилище не существует.")
            if Repo.inventory_exists(con, finding.inventory_code, finding_id):
                raise ValueError("Находка с таким инвентарным номером уже существует.")
            if finding_id is None:
                storage = Repo.one(con, "storages", finding.storage_id)
                if storage["capacity"]:
                    occupied = con.execute("SELECT COUNT(*) FROM findings WHERE storage_id=?",
                                           (finding.storage_id,)).fetchone()[0]
                    if occupied >= storage["capacity"]:
                        raise ValueError("В выбранном хранилище нет свободных мест.")
                new_id = Repo.insert_finding(con, rec)
                Repo.record_log(con, new_id, finding.inventory_code, "Создание", "Добавлена новая находка")
                return new_id
            old = Repo.one(con, "findings", finding_id)
            if not old:
                raise ValueError("Находка не найдена.")
            # A storage change must use the dedicated transfer workflow.
            rec["storage_id"] = old["storage_id"]
            Repo.update_finding(con, finding_id, rec)
            changed = [k for k, v in rec.items() if old[k] != v]
            if changed:
                Repo.record_log(con, finding_id, finding.inventory_code, "Изменение",
                                "Обновлены поля: " + ", ".join(changed))
            return finding_id

    def delete_finding(self, finding_id):
        with self._using() as con:
            old = Repo.one(con, "findings", finding_id)
            if not old:
                raise ValueError("Находка не найдена.")
            Repo.record_log(con, finding_id, old["inventory_code"], "Удаление",
                            "Удалена находка: " + old["title"])
            con.execute("DELETE FROM findings WHERE id=?", (finding_id,))

    def move_finding(self, finding_id, storage_id, reason):
        reason = require_text(reason, "Причина перемещения", 350)
        storage_id = int(storage_id)
        with self._using() as con:
            finding = Repo.one(con, "findings", finding_id)
            target = Repo.one(con, "storages", storage_id)
            if not finding or not target:
                raise ValueError("Находка или хранилище не найдены.")
            if finding["storage_id"] == storage_id:
                raise ValueError("Находка уже находится в выбранном хранилище.")
            origin_id = finding["storage_id"] #lol
            origin = Repo.one(con, "storages", origin_id)
            if target["capacity"]:
                occupancy = con.execute("SELECT COUNT(*) FROM findings WHERE storage_id=?", (storage_id,)).fetchone()[0]
                if occupancy >= target["capacity"]:
                    raise ValueError("В выбранном хранилище нет свободных мест.")
            con.execute("UPDATE findings SET storage_id=?,updated_at=datetime('now') WHERE id=?",
                        (storage_id, finding_id))
            Repo.record_movement(con, finding_id, finding["inventory_code"], origin_id, storage_id,
                                 origin["name"], target["name"], reason)
            Repo.record_log(con, finding_id, finding["inventory_code"], "Перемещение",
                            f"{origin['name']} → {target['name']}. {reason}")

    def save_site(self, raw, site_id=None):
        name = require_text(raw.get("name"), "Название участка", 120)
        region = require_text(raw.get("region"), "Регион", 120)
        period = str(raw.get("period") or "").strip()[:120]
        notes = str(raw.get("notes") or "").strip()[:1000]
        with self._using() as con:
            if site_id is None:
                con.execute("INSERT INTO sites(name,region,period,notes) VALUES(?,?,?,?)",
                            (name, region, period, notes))
            else:
                if not Repo.one(con, "sites", site_id):
                    raise ValueError("Участок не найден.")
                con.execute("UPDATE sites SET name=?,region=?,period=?,notes=? WHERE id=?",
                            (name, region, period, notes, site_id))

    def delete_site(self, site_id):
        with self._using() as con:
            if not Repo.one(con, "sites", site_id):
                raise ValueError("Участок не найден.")
            if con.execute("SELECT COUNT(*) FROM findings WHERE site_id=?", (site_id,)).fetchone()[0]:
                raise ValueError("Нельзя удалить участок, пока на нём числятся находки.")
            con.execute("DELETE FROM sites WHERE id=?", (site_id,))

    def save_storage(self, raw, storage_id=None):
        name = require_text(raw.get("name"), "Название хранилища", 120)
        location = require_text(raw.get("location"), "Расположение", 150)
        capacity = parse_nonnegative_int(raw.get("capacity", 0), "Вместимость")
        notes = str(raw.get("notes") or "").strip()[:1000]
        with self._using() as con:
            if storage_id is not None:
                if not Repo.one(con, "storages", storage_id):
                    raise ValueError("Хранилище не найдено.")
                occupied = con.execute("SELECT COUNT(*) FROM findings WHERE storage_id=?", (storage_id,)).fetchone()[0]
                if capacity and occupied > capacity:
                    raise ValueError("Вместимость меньше текущего числа находок.")
                con.execute("UPDATE storages SET name=?,location=?,capacity=?,notes=? WHERE id=?",
                            (name, location, capacity, notes, storage_id))
            else:
                con.execute("INSERT INTO storages(name,location,capacity,notes) VALUES(?,?,?,?)",
                            (name, location, capacity, notes))

    def delete_storage(self, storage_id):
        with self._using() as con:
            if not Repo.one(con, "storages", storage_id):
                raise ValueError("Хранилище не найдено.")
            if con.execute("SELECT COUNT(*) FROM findings WHERE storage_id=?", (storage_id,)).fetchone()[0]:
                raise ValueError("Сначала переместите находки в другое хранилище.")
            con.execute("DELETE FROM storages WHERE id=?", (storage_id,))

    def create_lab_request(self, finding_id, laboratory, start, end, purpose):
        laboratory = require_text(laboratory, "Лаборатория", 150)
        purpose = require_text(purpose, "Цель анализа", 500)
        start, end = validate_lab_dates(start, end)
        with self._using() as con:
            found = Repo.one(con, "findings", finding_id)
            if not found:
                raise ValueError("Находка не найдена.")
            for existing in Repo.active_lab_periods(con, finding_id):
                if periods_overlap(start, end, existing["start_date"], existing["end_date"]):
                    raise ValueError("Для этой находки уже назначен анализ на пересекающиеся даты.")
            lab_id = con.execute("""INSERT INTO lab_requests(finding_id,inventory_snapshot,laboratory,
                start_date,end_date,status,purpose) VALUES(?,?,?,?,?,'Назначен',?)""",
                (finding_id, found["inventory_code"], laboratory, start, end, purpose)).lastrowid
            Repo.record_log(con, finding_id, found["inventory_code"], "Лаборатория",
                            f"Анализ №{lab_id}: {laboratory}, {start} — {end}")
            return lab_id

    def update_lab_status(self, lab_id, status, result=""):
        if status not in LAB_STATUSES:
            raise ValueError("Недопустимый статус анализа.")
        result = str(result or "").strip()
        with self._using() as con:
            old = Repo.one(con, "lab_requests", lab_id)
            if not old:
                raise ValueError("Заявка не найдена.")
            if status in ACTIVE_LAB_STATUSES and old["status"] not in ACTIVE_LAB_STATUSES and old["finding_id"]:
                for another in Repo.active_lab_periods(con, old["finding_id"]):
                    if another["id"] != lab_id and periods_overlap(old["start_date"], old["end_date"],
                                                                     another["start_date"], another["end_date"]):
                        raise ValueError("Нельзя возобновить заявку: даты пересекаются с другим анализом.")
            con.execute("UPDATE lab_requests SET status=?,result=?,updated_at=datetime('now') WHERE id=?",
                        (status, result, lab_id))
            Repo.record_log(con, old["finding_id"], old["inventory_snapshot"], "Лаборатория",
                            f"Заявка №{lab_id}: статус «{status}»")

    def export_findings(self, path, filters=None, sort_by="code", descending=False):
        rows = self.list_findings(filters, sort_by, descending)
        return export_findings_csv(rows, path)
