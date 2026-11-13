"""Tkinter desktop interface for the field archive."""
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox, filedialog
from config import (
    APP_TITLE, CATEGORIES, CONDITIONS, LAB_STATUSES, SORT_LABELS,
)

BG = "#f3f6fb"
SURFACE = "#ffffff"
INK = "#1c2c43"
MUTED = "#64748b"
ACCENT = "#255ac8"
BORDER = "#dde4ee"


def action_button(parent, text, command, primary=False):
    return ttk.Button(parent, text=text, command=command,
                      style="Primary.TButton" if primary else "TButton")


def labeled_field(parent, label, widget, row, col=0, col_span=1):
    ttk.Label(parent, text=label, style="FormLabel.TLabel").grid(
        row=row * 2, column=col, columnspan=col_span, sticky="w", pady=(7, 3), padx=(0, 14))
    widget.grid(row=row * 2 + 1, column=col, columnspan=col_span, sticky="ew", padx=(0, 14), pady=(0, 4))


class EditorDialog(tk.Toplevel):
    """Reused layout for validated entity editors."""
    def __init__(self, master, title, width=650):
        super().__init__(master)
        self.title(title)
        self.configure(bg=BG)
        self.transient(master)
        self.resizable(True, True)
        self.minsize(width, 380)
        self.result = False
        self.body = ttk.Frame(self, padding=(24, 20), style="Panel.TFrame")
        self.body.pack(fill="both", expand=True, padx=14, pady=14)
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=1)
        self.controls = {}
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()

    def entry(self, name, label, row, col=0, initial="", width=28):
        value = tk.StringVar(value=str(initial if initial is not None else ""))
        widget = ttk.Entry(self.body, textvariable=value, width=width)
        labeled_field(self.body, label, widget, row, col)
        self.controls[name] = value
        return widget

    def combo(self, name, label, row, col=0, values=(), initial=""):
        value = tk.StringVar(value=str(initial if initial is not None else ""))
        widget = ttk.Combobox(self.body, textvariable=value, values=list(values), state="readonly", width=26)
        labeled_field(self.body, label, widget, row, col)
        self.controls[name] = value
        return widget

    def multiline(self, name, label, row, value="", height=4):
        widget = tk.Text(self.body, height=height, wrap="word", relief="solid", bd=1,
                         bg=SURFACE, fg=INK, font=("Segoe UI", 10))
        widget.insert("1.0", str(value or ""))
        labeled_field(self.body, label, widget, row, 0, 2)
        self.controls[name] = widget

    def values(self):
        return {key: (ctrl.get("1.0", "end-1c") if isinstance(ctrl, tk.Text) else ctrl.get())
                for key, ctrl in self.controls.items()}

    def buttons(self, callback):
        row = ttk.Frame(self.body, style="Panel.TFrame")
        row.grid(row=99, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(row, text="Отмена", command=self.destroy).pack(side="left", padx=(0, 10))
        action_button(row, "Сохранить", lambda: self._submit(callback), primary=True).pack(side="left")

    def _submit(self, callback):
        try:
            callback(self.values())
        except (ValueError, sqlite3.IntegrityError) as exc:
            messagebox.showerror("Проверьте данные", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Ошибка операции", f"Не удалось сохранить запись:\n{exc}", parent=self)
            return
        self.result = True
        self.destroy()


class ArchiveApp(tk.Tk):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.title(APP_TITLE)
        self.geometry("1380x830")
        self.minsize(1080, 670)
        self.configure(bg=BG)
        self._style()
        self._sites = []
        self._storages = []
        self._shown_findings = []
        self._make_header()
        self.tabs = ttk.Notebook(self, style="Main.TNotebook")
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(3, 14))
        self._make_findings_tab()
        self._make_sites_tab()
        self._make_storages_tab()
        self._make_labs_tab()
        self._make_movements_tab()
        self._make_history_tab()
        self._make_stats_tab()
        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status, background=BG, foreground=MUTED,
                  font=("Segoe UI", 9)).pack(fill="x", padx=22, pady=(0, 9))
        self.refresh_all()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI", 10))
        style.configure("FormLabel.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 22))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 12))
        style.configure("Metric.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 24))
        style.configure("MetricName.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 9), padding=(11, 7),
                        background=SURFACE, foreground=INK, borderwidth=1, bordercolor=BORDER)
        style.map("TButton", background=[("active", "#e9f0ff")])
        style.configure("Primary.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT)
        style.map("Primary.TButton", background=[("active", "#18429c")], foreground=[("active", "white")])
        style.configure("TEntry", padding=(7, 6), fieldbackground="white", bordercolor=BORDER)
        style.configure("TCombobox", padding=(7, 6), fieldbackground="white")
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 9), background=SURFACE,
                        fieldbackground=SURFACE, foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", background="#e8eef7", foreground=INK,
                        font=("Segoe UI Semibold", 9), padding=(9, 9), relief="flat")
        style.map("Treeview", background=[("selected", "#d5e5ff")], foreground=[("selected", INK)])
        style.configure("Main.TNotebook", background=BG, borderwidth=0)
        style.configure("Main.TNotebook.Tab", padding=(19, 12), background="#e9eef6", foreground=INK,
                        font=("Segoe UI Semibold", 10))
        style.map("Main.TNotebook.Tab", background=[("selected", SURFACE)],
                  foreground=[("selected", ACCENT)])

    def _make_header(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=24, pady=(17, 13))
        ttk.Label(header, text="ПОЛЕВОЙ АРХИВ", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="Каталог находок · археологические участки · хранение · лабораторные исследования",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

    def _tab(self, name):
        frame = ttk.Frame(self.tabs, padding=(15, 15, 15, 12))
        self.tabs.add(frame, text=name)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        return frame

    def _toolbar(self, parent):
        bar = ttk.Frame(parent)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        return bar

    def _table(self, parent, headers, row=1):
        area = ttk.Frame(parent, style="Panel.TFrame")
        area.grid(row=row, column=0, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        ids = list(headers)
        tree = ttk.Treeview(area, columns=ids, show="headings", selectmode="browse")
        for col, (title, width) in headers.items():
            tree.heading(col, text=title)
            tree.column(col, width=width, minwidth=65, anchor="w", stretch=col in ("title", "details", "notes"))
        tree.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(area, orient="vertical", command=tree.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar = ttk.Scrollbar(area, orient="horizontal", command=tree.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.tag_configure("even", background="#f6f9fe")
        return tree

    @staticmethod
    def _populate(tree, rows, mapper):
        tree.delete(*tree.get_children())
        for i, row in enumerate(rows):
            tree.insert("", "end", iid=str(row["id"]), values=mapper(row),
                        tags=("even",) if i % 2 == 0 else ())

    @staticmethod
    def _selected(tree):
        selected = tree.selection()
        return int(selected[0]) if selected else None

    def _required(self, tree, name):
        selected = self._selected(tree)
        if selected is None:
            messagebox.showinfo("Выбор записи", f"Сначала выберите {name} в таблице.", parent=self)
        return selected

    def _perform(self, action, success="Изменения сохранены"):
        try:
            action()
            self.refresh_all()
            self.status.set(success)
        except (ValueError, sqlite3.IntegrityError) as exc:
            messagebox.showerror("Проверьте данные", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("Ошибка операции", str(exc), parent=self)

    def _make_findings_tab(self):
        frame = self._tab("Находки")
        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        controls = ttk.Frame(top)
        controls.pack(fill="x")
        action_button(controls, "+ Новая находка", self.add_finding, primary=True).pack(side="left", padx=(0, 7))
        action_button(controls, "Редактировать", self.edit_finding).pack(side="left", padx=5)
        action_button(controls, "Удалить", self.delete_finding).pack(side="left", padx=5)
        action_button(controls, "Переместить", self.move_finding).pack(side="left", padx=5)
        action_button(controls, "В лабораторию", self.lab_for_finding).pack(side="left", padx=5)
        action_button(controls, "Экспорт CSV", self.export_csv).pack(side="left", padx=5)
        action_button(controls, "Обновить", self.refresh_all).pack(side="right")
        filters = ttk.Frame(top)
        filters.pack(fill="x", pady=(12, 0))
        self.q_name = tk.StringVar()
        self.q_category = tk.StringVar(value="Все категории")
        self.q_site = tk.StringVar(value="Все участки")
        self.q_storage = tk.StringVar(value="Все хранилища")
        self.q_min = tk.StringVar()
        self.q_max = tk.StringVar()
        self.q_sort = tk.StringVar(value="Инвентарный номер")
        self.q_desc = tk.BooleanVar(value=False)
        widgets = [
            ("Поиск: название или код", ttk.Entry(filters, textvariable=self.q_name, width=24)),
            ("Категория", ttk.Combobox(filters, textvariable=self.q_category, width=19,
                                       values=["Все категории", *CATEGORIES], state="readonly")),
            ("Участок", ttk.Combobox(filters, textvariable=self.q_site, width=25, state="readonly")),
            ("Хранилище", ttk.Combobox(filters, textvariable=self.q_storage, width=24, state="readonly")),
            ("Глубина от", ttk.Entry(filters, textvariable=self.q_min, width=10)),
            ("Глубина до", ttk.Entry(filters, textvariable=self.q_max, width=10)),
        ]
        for idx, (label, widget) in enumerate(widgets):
            ttk.Label(filters, text=label).grid(row=0, column=idx, sticky="w", padx=(0, 7))
            widget.grid(row=1, column=idx, sticky="ew", padx=(0, 8), pady=(4, 0))
            if idx in (2, 3):
                if idx == 2:
                    self.site_filter_combo = widget
                else:
                    self.storage_filter_combo = widget
        filters.columnconfigure(0, weight=2)
        filters.columnconfigure(2, weight=1)
        sortbar = ttk.Frame(top)
        sortbar.pack(fill="x", pady=(10, 0))
        ttk.Label(sortbar, text="Сортировка").pack(side="left", padx=(0, 8))
        ttk.Combobox(sortbar, textvariable=self.q_sort, width=22, state="readonly",
                     values=list(SORT_LABELS)).pack(side="left", padx=(0, 9))
        ttk.Checkbutton(sortbar, text="По убыванию", variable=self.q_desc).pack(side="left", padx=(0, 16))
        action_button(sortbar, "Применить фильтры", self.refresh_findings, primary=True).pack(side="left", padx=(0, 8))
        action_button(sortbar, "Сбросить", self.reset_filters).pack(side="left")
        self.find_count = ttk.Label(sortbar, text="", foreground=MUTED)
        self.find_count.pack(side="right", padx=8)
        self.find_tree = self._table(frame, {
            "code": ("Инв. номер", 138), "title": ("Наименование", 220),
            "category": ("Категория", 130), "site": ("Участок", 175),
            "depth": ("Глубина, см", 95), "age": ("Возраст, лет", 103),
            "storage": ("Хранилище", 176), "date": ("Обнаружено", 105),
        })
        self.find_tree.bind("<Double-1>", lambda _: self.edit_finding())
        self.q_name_entry = widgets[0][1]
        self.q_name_entry.bind("<Return>", lambda _: self.refresh_findings())

    def _filters(self):
        sites = {s["name"]: s["id"] for s in self._sites}
        storages = {s["name"]: s["id"] for s in self._storages}
        return {
            "name": self.q_name.get().strip(),
            "category": "" if self.q_category.get() == "Все категории" else self.q_category.get(),
            "site_id": sites.get(self.q_site.get()),
            "storage_id": storages.get(self.q_storage.get()),
            "min_depth": self.q_min.get().strip(),
            "max_depth": self.q_max.get().strip(),
        }

    def refresh_findings(self):
        try:
            rows = self.service.list_findings(self._filters(), SORT_LABELS[self.q_sort.get()], self.q_desc.get())
        except ValueError as exc:
            messagebox.showerror("Ошибка фильтра", str(exc), parent=self)
            return
        self._shown_findings = rows
        self._populate(self.find_tree, rows, lambda x: (
            x["inventory_code"], x["title"], x["category"], x["site_name"],
            f'{x["depth_cm"]:g}', x["age_years"], x["storage_name"], x["discovery_date"],
        ))
        self.find_count.configure(text=f"Записей: {len(rows)}")

    def reset_filters(self):
        self.q_name.set("")
        self.q_category.set("Все категории")
        self.q_site.set("Все участки")
        self.q_storage.set("Все хранилища")
        self.q_min.set("")
        self.q_max.set("")
        self.q_sort.set("Инвентарный номер")
        self.q_desc.set(False)
        self.refresh_findings()

    def _finding_dialog(self, current=None):
        d = EditorDialog(self, "Редактирование находки" if current else "Регистрация находки", 790)
        d.geometry("800x760")
        data = current or {}
        get = lambda key, default="": data.get(key, default)
        d.entry("inventory_code", "Инвентарный номер", 0, 0, get("inventory_code"))
        d.entry("title", "Наименование", 0, 1, get("title"))
        d.combo("category", "Категория", 1, 0, CATEGORIES, get("category", CATEGORIES[0]))
        d.combo("condition", "Сохранность", 1, 1, CONDITIONS, get("condition", CONDITIONS[0]))
        site_names = {s["id"]: s["name"] for s in self._sites}
        storage_names = {s["id"]: s["name"] for s in self._storages}
        d.combo("site_name", "Археологический участок", 2, 0, list(site_names.values()),
                site_names.get(get("site_id"), next(iter(site_names.values()), "")))
        storage_widget = d.combo("storage_name", "Хранилище (для изменения — «Переместить»)", 2, 1,
                                 list(storage_names.values()),
                                 storage_names.get(get("storage_id"), next(iter(storage_names.values()), "")))
        if current:
            storage_widget.configure(state="disabled")
        d.entry("discovery_date", "Дата обнаружения, ГГГГ-ММ-ДД", 3, 0,
                get("discovery_date", date.today().isoformat()))
        d.entry("material", "Материал", 3, 1, get("material"))
        d.entry("depth_cm", "Глубина, см", 4, 0, get("depth_cm", "0"))
        d.entry("age_years", "Предполагаемый возраст, лет", 4, 1, get("age_years", "0"))
        d.multiline("description", "Описание / примечания", 5, get("description"), height=5)
        site_ids = {v: k for k, v in site_names.items()}
        storage_ids = {v: k for k, v in storage_names.items()}
        def save(raw):
            raw["site_id"] = site_ids.get(raw.pop("site_name"))
            raw["storage_id"] = storage_ids.get(raw.pop("storage_name"))
            self.service.save_finding(raw, data.get("id"))
        d.buttons(save)
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def add_finding(self):
        self._finding_dialog()

    def edit_finding(self):
        item_id = self._required(self.find_tree, "находку")
        if item_id is not None:
            self._finding_dialog(self.service.get_finding(item_id))

    def delete_finding(self):
        item_id = self._required(self.find_tree, "находку")
        if item_id is None:
            return
        if messagebox.askyesno("Удаление находки", "Удалить выбранную находку? Операция необратима.", parent=self):
            self._perform(lambda: self.service.delete_finding(item_id), "Находка удалена")

    def move_finding(self):
        item_id = self._required(self.find_tree, "находку")
        if item_id is None:
            return
        found = self.service.get_finding(item_id)
        d = EditorDialog(self, f"Перемещение: {found['inventory_code']}")
        d.geometry("660x430")
        storage_names = {s["name"]: s["id"] for s in self._storages}
        current = next((name for name, sid in storage_names.items() if sid == found["storage_id"]), "")
        d.combo("storage", "Новое хранилище", 0, 0, storage_names, current)
        d.entry("reason", "Основание для перемещения", 1, 0)
        d.buttons(lambda data: self.service.move_finding(item_id, storage_names[data["storage"]], data["reason"]))
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def export_csv(self):
        path = filedialog.asksaveasfilename(parent=self, title="Экспорт текущего списка",
                                            initialfile="archaeology_export.csv", defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            self._perform(lambda: self.service.export_findings(path, self._filters(),
                          SORT_LABELS[self.q_sort.get()], self.q_desc.get()), "CSV успешно сохранён")

    def _make_sites_tab(self):
        tab = self._tab("Участки")
        bar = self._toolbar(tab)
        action_button(bar, "+ Добавить участок", self.add_site, primary=True).pack(side="left", padx=(0, 6))
        action_button(bar, "Редактировать", self.edit_site).pack(side="left", padx=6)
        action_button(bar, "Удалить", self.delete_site).pack(side="left", padx=6)
        self.site_tree = self._table(tab, {
            "name": ("Название участка", 275), "region": ("Регион", 220),
            "period": ("Исторический период", 190), "notes": ("Примечания", 350),
        })
        self.site_tree.bind("<Double-1>", lambda _: self.edit_site())

    def _site_dialog(self, current=None):
        d = EditorDialog(self, "Археологический участок")
        d.geometry("680x480")
        data = current or {}
        d.entry("name", "Название участка", 0, 0, data.get("name", ""))
        d.entry("region", "Регион", 0, 1, data.get("region", ""))
        d.entry("period", "Исторический период", 1, 0, data.get("period", ""))
        d.multiline("notes", "Описание участка", 2, data.get("notes", ""), 4)
        d.buttons(lambda raw: self.service.save_site(raw, data.get("id")))
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def add_site(self):
        self._site_dialog()

    def edit_site(self):
        item_id = self._required(self.site_tree, "участок")
        if item_id is not None:
            self._site_dialog(next(s for s in self._sites if s["id"] == item_id))

    def delete_site(self):
        item_id = self._required(self.site_tree, "участок")
        if item_id is not None and messagebox.askyesno("Удаление", "Удалить участок?", parent=self):
            self._perform(lambda: self.service.delete_site(item_id))

    def _make_storages_tab(self):
        tab = self._tab("Хранилища")
        bar = self._toolbar(tab)
        action_button(bar, "+ Добавить хранилище", self.add_storage, primary=True).pack(side="left", padx=(0, 6))
        action_button(bar, "Редактировать", self.edit_storage).pack(side="left", padx=6)
        action_button(bar, "Удалить", self.delete_storage).pack(side="left", padx=6)
        self.storage_tree = self._table(tab, {
            "name": ("Хранилище", 265), "location": ("Расположение", 245),
            "capacity": ("Вместимость (0 = без лимита)", 215), "notes": ("Примечания", 345),
        })
        self.storage_tree.bind("<Double-1>", lambda _: self.edit_storage())

    def _storage_dialog(self, current=None):
        d = EditorDialog(self, "Хранилище")
        d.geometry("680x475")
        data = current or {}
        d.entry("name", "Название", 0, 0, data.get("name", ""))
        d.entry("location", "Расположение", 0, 1, data.get("location", ""))
        d.entry("capacity", "Вместимость (0 = без лимита)", 1, 0, data.get("capacity", "0"))
        d.multiline("notes", "Примечания", 2, data.get("notes", ""), 4)
        d.buttons(lambda raw: self.service.save_storage(raw, data.get("id")))
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def add_storage(self):
        self._storage_dialog()

    def edit_storage(self):
        item_id = self._required(self.storage_tree, "хранилище")
        if item_id is not None:
            self._storage_dialog(next(s for s in self._storages if s["id"] == item_id))

    def delete_storage(self):
        item_id = self._required(self.storage_tree, "хранилище")
        if item_id is not None and messagebox.askyesno("Удаление", "Удалить хранилище?", parent=self):
            self._perform(lambda: self.service.delete_storage(item_id))

    def _make_labs_tab(self):
        tab = self._tab("Лаборатория")
        bar = self._toolbar(tab)
        action_button(bar, "+ Направить на анализ", self.add_lab, primary=True).pack(side="left", padx=(0, 6))
        action_button(bar, "Изменить статус и результат", self.change_lab).pack(side="left", padx=6)
        action_button(bar, "Обновить", self.refresh_all).pack(side="right")
        self.lab_tree = self._table(tab, {
            "code": ("Инв. номер", 135), "lab": ("Лаборатория", 235),
            "from": ("Начало", 95), "to": ("Окончание", 95),
            "status": ("Статус", 125), "purpose": ("Цель анализа", 275),
            "result": ("Результат", 265),
        })
        self.lab_tree.bind("<Double-1>", lambda _: self.change_lab())

    def lab_for_finding(self):
        finding_id = self._required(self.find_tree, "находку")
        if finding_id is not None:
            self._lab_dialog(finding_id)

    def add_lab(self):
        self._lab_dialog()

    def _lab_dialog(self, finding_id=None):
        findings = self.service.list_findings()
        display = {f'{r["inventory_code"]} — {r["title"]}': r["id"] for r in findings}
        if not display:
            messagebox.showinfo("Лаборатория", "Сначала создайте находку.", parent=self)
            return
        current_display = next((key for key, val in display.items() if val == finding_id), next(iter(display)))
        d = EditorDialog(self, "Передача на лабораторный анализ", 720)
        d.geometry("750x490")
        d.combo("finding", "Находка", 0, 0, display, current_display)
        d.entry("laboratory", "Лаборатория", 0, 1, "Лаборатория материалов")
        d.entry("start", "Начало (ГГГГ-ММ-ДД)", 1, 0, date.today().isoformat())
        d.entry("end", "Окончание (ГГГГ-ММ-ДД)", 1, 1, date.today().isoformat())
        d.multiline("purpose", "Цель лабораторного исследования", 2, "Исследование состава", 3)
        d.buttons(lambda x: self.service.create_lab_request(
            display[x["finding"]], x["laboratory"], x["start"], x["end"], x["purpose"]))
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def change_lab(self):
        item_id = self._required(self.lab_tree, "лабораторную заявку")
        if item_id is None:
            return
        record = next(r for r in self.service.list_labs() if r["id"] == item_id)
        d = EditorDialog(self, f"Результат лаборатории: заявка №{item_id}")
        d.geometry("670x420")
        d.combo("status", "Статус", 0, 0, LAB_STATUSES, record["status"])
        d.multiline("result", "Результат / примечания", 1, record["result"], 5)
        d.buttons(lambda x: self.service.update_lab_status(item_id, x["status"], x["result"]))
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def _make_movements_tab(self):
        tab = self._tab("Перемещения")
        bar = self._toolbar(tab)
        ttk.Label(bar, text="История передачи находок между хранилищами",
                  style="Section.TLabel").pack(side="left")
        action_button(bar, "Обновить", self.refresh_all).pack(side="right")
        self.move_tree = self._table(tab, {
            "code": ("Инв. номер", 135), "origin": ("Откуда", 260),
            "target": ("Куда", 260), "reason": ("Основание", 305),
            "when": ("Дата и время", 175),
        })

    def _make_history_tab(self):
        tab = self._tab("История изменений")
        bar = self._toolbar(tab)
        ttk.Label(bar, text="Журнал изменений каталога", style="Section.TLabel").pack(side="left")
        action_button(bar, "Обновить", self.refresh_all).pack(side="right")
        self.history_tree = self._table(tab, {
            "code": ("Инв. номер", 140), "action": ("Операция", 155),
            "details": ("Описание изменения", 665), "time": ("Дата и время", 175),
        })

    def _make_stats_tab(self):
        tab = self._tab("Статистика")
        heading = self._toolbar(tab)
        ttk.Label(heading, text="Обзор состояния коллекции", style="Section.TLabel").pack(side="left")
        action_button(heading, "Обновить статистику", self.refresh_all).pack(side="right")
        contents = ttk.Frame(tab)
        contents.grid(row=1, column=0, sticky="nsew")
        contents.columnconfigure((0, 1, 2), weight=1)
        contents.rowconfigure(1, weight=1)
        self.metrics = {}
        titles = [("total", "Всего находок"), ("sites", "Участков"),
                  ("active_labs", "Анализов в работе"), ("average_depth", "Средняя глубина, см")]
        metrics_row = ttk.Frame(contents)
        metrics_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        for i, (key, label) in enumerate(titles):
            metrics_row.columnconfigure(i, weight=1)
            panel = ttk.Frame(metrics_row, padding=(18, 16), style="Panel.TFrame")
            panel.grid(row=0, column=i, sticky="ew", padx=(0, 10))
            ttk.Label(panel, text=label, style="MetricName.TLabel").pack(anchor="w")
            metric = ttk.Label(panel, text="—", style="Metric.TLabel")
            metric.pack(anchor="w", pady=(3, 0))
            self.metrics[key] = metric
        views = [
            ("Категории", "category_tree"),
            ("Археологические участки", "site_stats_tree"),
            ("Заполняемость хранилищ", "storage_stats_tree"),
        ]
        for i, (title, attr) in enumerate(views):
            block = ttk.Frame(contents, style="Panel.TFrame", padding=(14, 13))
            block.grid(row=1, column=i, sticky="nsew", padx=(0, 10))
            block.columnconfigure(0, weight=1)
            block.rowconfigure(1, weight=1)
            ttk.Label(block, text=title, style="Panel.TLabel",
                      font=("Segoe UI Semibold", 11)).grid(row=0, column=0, sticky="w", pady=(0, 10))
            tree = ttk.Treeview(block, columns=("name", "qty"), show="headings", height=14)
            tree.heading("name", text="Наименование")
            tree.heading("qty", text="Кол-во")
            tree.column("name", width=210, stretch=True)
            tree.column("qty", width=80, anchor="center", stretch=False)
            tree.grid(row=1, column=0, sticky="nsew")
            scroll = ttk.Scrollbar(block, orient="vertical", command=tree.yview)
            scroll.grid(row=1, column=1, sticky="ns")
            tree.configure(yscrollcommand=scroll.set)
            setattr(self, attr, tree)
        self.lab_stats = ttk.Label(contents, text="", style="Subtitle.TLabel")
        self.lab_stats.grid(row=2, column=0, columnspan=3, sticky="w", pady=(15, 0))

    def refresh_all(self):
        self._sites = self.service.list_sites()
        self._storages = self.service.list_storages()
        self._populate(self.site_tree, self._sites,
                       lambda x: (x["name"], x["region"], x["period"], x["notes"]))
        self._populate(self.storage_tree, self._storages,
                       lambda x: (x["name"], x["location"], x["capacity"], x["notes"]))
        site_choices = ["Все участки"] + [s["name"] for s in self._sites]
        storage_choices = ["Все хранилища"] + [s["name"] for s in self._storages]
        self.site_filter_combo.configure(values=site_choices)
        self.storage_filter_combo.configure(values=storage_choices)
        if self.q_site.get() not in site_choices:
            self.q_site.set(site_choices[0])
        if self.q_storage.get() not in storage_choices:
            self.q_storage.set(storage_choices[0])
        self.refresh_findings()
        self._populate(self.move_tree, self.service.list_movements(), lambda x: (
            x["inventory_snapshot"], x["from_storage_name"], x["to_storage_name"],
            x["reason"], x["moved_at"],
        ))
        self._populate(self.lab_tree, self.service.list_labs(), lambda x: (
            x["inventory_snapshot"], x["laboratory"], x["start_date"], x["end_date"],
            x["status"], x["purpose"], x["result"],
        ))
        self._populate(self.history_tree, self.service.list_history(), lambda x: (
            x["inventory_snapshot"], x["action"], x["details"], x["created_at"],
        ))
        stats = self.service.stats()
        for key, label in self.metrics.items():
            label.configure(text=str(stats[key]))
        for tree, items, mapper in [
            (self.category_tree, stats["by_category"], lambda r: (r["name"], r["quantity"])),
            (self.site_stats_tree, stats["by_site"], lambda r: (r["name"], r["quantity"])),
            (self.storage_stats_tree, stats["by_storage"],
             lambda r: (r["name"], f'{r["quantity"]} / {r["capacity"] or "∞"}')),
        ]:
            tree.delete(*tree.get_children())
            for i, item in enumerate(items):
                tree.insert("", "end", iid=str(i), values=mapper(item))
        lab_text = ", ".join(f'{x["name"]}: {x["quantity"]}' for x in stats["by_lab"])
        self.lab_stats.configure(text="Лабораторные заявки — " + (lab_text or "нет"))
        self.status.set(f"Каталог обновлён · находок в базе: {stats['total']}")
