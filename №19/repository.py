"""SQL read/write operations; use a shared connection for each transaction."""


class ArchiveRepository:
    FINDING_SORT = {
        "code": "f.inventory_code COLLATE NOCASE",
        "title": "f.title COLLATE NOCASE",
        "depth": "f.depth_cm", #fhfgh
        "age": "f.age_years",
        "date": "f.discovery_date",
        "site": "s.name COLLATE NOCASE",
        "storage": "st.name COLLATE NOCASE",
    }

    @staticmethod
    def one(con, table, item_id):
        if table not in ("findings", "sites", "storages", "lab_requests"):
            raise ValueError("Недопустимый тип записи")
        row = con.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_findings(con, filters=None, sort_by="code", descending=False):
        filters = filters or {}
        sql = """SELECT f.*, s.name AS site_name, st.name AS storage_name
                 FROM findings f
                 JOIN sites s ON s.id = f.site_id
                 JOIN storages st ON st.id = f.storage_id"""
        clauses, params = [], []
        query = str(filters.get("name") or "").strip()
        category = str(filters.get("category") or "").strip()
        if query:
            clauses.append("(f.title LIKE ? COLLATE NOCASE OR f.inventory_code LIKE ? COLLATE NOCASE)")
            params.extend([f"%{query}%", f"%{query}%"])
        if category:
            clauses.append("f.category = ?")
            params.append(category)
        for field, column in (("site_id", "f.site_id"), ("storage_id", "f.storage_id")):
            if filters.get(field) not in (None, ""):
                clauses.append(f"{column} = ?")
                params.append(int(filters[field]))
        for field, column, op in (("min_depth", "f.depth_cm", ">="), ("max_depth", "f.depth_cm", "<=")):
            if filters.get(field) not in (None, ""):
                clauses.append(f"{column} {op} ?")
                params.append(float(filters[field]))
        if clauses: #lollll
            sql += " WHERE " + " AND ".join(clauses)
        order_expr = ArchiveRepository.FINDING_SORT.get(sort_by, ArchiveRepository.FINDING_SORT["code"])
        sql += f" ORDER BY {order_expr} {'DESC' if descending else 'ASC'}, f.id ASC"
        return [dict(row) for row in con.execute(sql, params)]

    @staticmethod
    def list_sites(con):
        return [dict(r) for r in con.execute("SELECT * FROM sites ORDER BY name COLLATE NOCASE")]

    @staticmethod
    def list_storages(con):
        return [dict(r) for r in con.execute("SELECT * FROM storages ORDER BY name COLLATE NOCASE")]

    @staticmethod
    def list_movements(con):
        return [dict(r) for r in con.execute("SELECT * FROM movements ORDER BY id DESC")]

    @staticmethod
    def latest_movement(con, finding_id):
        row = con.execute("SELECT * FROM movements WHERE finding_id=? ORDER BY id DESC LIMIT 1", (finding_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_history(con):
        return [dict(r) for r in con.execute("SELECT * FROM change_logs ORDER BY id DESC")]

    @staticmethod
    def list_labs(con):
        return [dict(r) for r in con.execute("SELECT * FROM lab_requests ORDER BY id DESC")]

    @staticmethod
    def active_lab_periods(con, finding_id):
        return [dict(r) for r in con.execute("""SELECT * FROM lab_requests WHERE finding_id=?
             AND status IN ('Назначен', 'В работе') ORDER BY start_date""", (finding_id,))]

    @staticmethod
    def inventory_exists(con, code, exclude_id=None):
        if exclude_id is None:
            return con.execute("SELECT id FROM findings WHERE inventory_code=?", (code,)).fetchone() is not None
        return con.execute("SELECT id FROM findings WHERE inventory_code=? AND id<>?", (code, exclude_id)).fetchone() is not None

    @staticmethod
    def insert_finding(con, record):
        keys = list(record)
        cols = ", ".join(keys)
        qs = ", ".join("?" for _ in keys)
        return con.execute(f"INSERT INTO findings ({cols}) VALUES ({qs})", [record[k] for k in keys]).lastrowid

    @staticmethod
    def update_finding(con, finding_id, record):
        keys = list(record)
        assignments = ", ".join(f"{key}=?" for key in keys)
        con.execute(f"UPDATE findings SET {assignments}, updated_at=datetime('now') WHERE id=?",
                    [record[k] for k in keys] + [finding_id])

    @staticmethod
    def record_log(con, finding_id, code, action, details):
        con.execute("""INSERT INTO change_logs(finding_id, inventory_snapshot, action, details)
                       VALUES(?, ?, ?, ?)""", (finding_id, code, action, details))

    @staticmethod
    def record_movement(con, finding_id, code, from_id, to_id, from_name, to_name, reason):
        con.execute("""INSERT INTO movements(finding_id,inventory_snapshot,from_storage_id,to_storage_id,
                       from_storage_name,to_storage_name,reason) VALUES(?,?,?,?,?,?,?)""",
                    (finding_id, code, from_id, to_id, from_name, to_name, reason))
