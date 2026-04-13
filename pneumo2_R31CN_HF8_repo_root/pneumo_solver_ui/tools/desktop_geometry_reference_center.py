from __future__ import annotations

import math
import os
import tkinter as tk
from tkinter import filedialog, ttk

from pneumo_solver_ui.desktop_ui_core import build_status_strip, create_scrollable_tab
from pneumo_solver_ui.desktop_geometry_reference_model import (
    CylinderCatalogRow,
    CylinderFamilyReferenceRow,
    build_cylinder_force_bias_estimate,
    CylinderMatchRecommendation,
    CylinderPackageReferenceRow,
    CylinderPrechargeReferenceRow,
    ComponentFitReferenceRow,
    SpringFamilyReferenceRow,
)
from pneumo_solver_ui.desktop_geometry_reference_runtime import DesktopGeometryReferenceRuntime
from pneumo_solver_ui.spring_table import build_spring_geometry_reference
from pneumo_solver_ui.suspension_family_contract import (
    FAMILY_ORDER,
    family_name,
    spring_static_mode_description,
)

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


class DesktopGeometryReferenceCenter:
    def __init__(self, host: tk.Misc | None = None, *, hosted: bool = False) -> None:
        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else tk.Tk()
        if self._owns_root:
            self.root.title(f"Справочный центр геометрии и компонентов ({RELEASE})")
            self.root.geometry("1540x980")
            self.root.minsize(1260, 820)

        self.runtime = DesktopGeometryReferenceRuntime()
        self._host_closed = False
        self._spring_inputs_seeded = False

        family_names = tuple(family_name(cyl, axle) for cyl, axle in FAMILY_ORDER)
        self.base_path_var = tk.StringVar(master=self.root, value=str(self.runtime.base_path))
        self.status_var = tk.StringVar(
            master=self.root,
            value="Справочный центр готов: геометрия, цилиндры, пружины и инженерные подсказки собраны в одном окне.",
        )
        self.geometry_summary_var = tk.StringVar(master=self.root)
        self.component_fit_summary_var = tk.StringVar(master=self.root)
        self.dw_min_var = tk.DoubleVar(master=self.root, value=-100.0)
        self.dw_max_var = tk.DoubleVar(master=self.root, value=100.0)

        self.cylinder_family_var = tk.StringVar(master=self.root, value=family_names[0])
        self.cylinder_variant_var = tk.StringVar(master=self.root, value="Все варианты")
        self.cylinder_search_var = tk.StringVar(master=self.root, value="")
        self.cylinder_pressure_var = tk.DoubleVar(master=self.root, value=6.0)
        self.cylinder_context_var = tk.StringVar(master=self.root)
        self.cylinder_choice_var = tk.StringVar(master=self.root)
        self.cylinder_recommendation_var = tk.StringVar(master=self.root)
        self.cylinder_precharge_summary_var = tk.StringVar(master=self.root)

        self.spring_family_var = tk.StringVar(master=self.root, value=family_names[0])
        self.spring_static_mode_var = tk.StringVar(master=self.root)
        self.spring_wire_var = tk.DoubleVar(master=self.root, value=8.0)
        self.spring_mean_diameter_var = tk.DoubleVar(master=self.root, value=60.0)
        self.spring_active_turns_var = tk.DoubleVar(master=self.root, value=8.0)
        self.spring_total_turns_var = tk.DoubleVar(master=self.root, value=10.0)
        self.spring_pitch_var = tk.DoubleVar(master=self.root, value=0.0)
        self.spring_g_var = tk.DoubleVar(master=self.root, value=79.0)
        self.spring_force_var = tk.DoubleVar(master=self.root, value=15000.0)
        self.spring_summary_var = tk.StringVar(master=self.root)
        self.spring_install_summary_var = tk.StringVar(master=self.root)

        self.guide_query_var = tk.StringVar(master=self.root, value="")
        self.guide_summary_var = tk.StringVar(master=self.root)

        self._catalog_rows_by_iid: dict[str, CylinderCatalogRow] = {}
        self._recommendations_by_iid: dict[str, CylinderMatchRecommendation] = {}
        self._current_cylinder_rows_by_family: dict[str, CylinderFamilyReferenceRow] = {}
        self._current_cylinder_package_rows_by_family: dict[str, CylinderPackageReferenceRow] = {}
        self._current_cylinder_precharge_rows_by_family: dict[str, CylinderPrechargeReferenceRow] = {}
        self._component_fit_rows_by_family: dict[str, ComponentFitReferenceRow] = {}
        self._current_spring_rows_by_family: dict[str, SpringFamilyReferenceRow] = {}

        self._build_ui(family_names=family_names)
        self.refresh_all()

    def _build_ui(self, *, family_names: tuple[str, ...]) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Справочный центр геометрии и компонентов",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Отдельный справочно-инженерный рабочий центр для анализа геометрии подвески, "
                "подбора цилиндров, расчёта геометрии пружин и быстрого доступа к параметрам. "
                "Центр не редактирует исходные данные напрямую и не повторяет web-компоновку; он помогает принимать инженерные решения."
            ),
            wraplength=1420,
            justify="left",
        ).pack(anchor="w", pady=(6, 10))

        source = ttk.LabelFrame(outer, text="Источник опорных данных", padding=10)
        source.pack(fill="x", expand=False)
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Базовый JSON:").grid(row=0, column=0, sticky="w")
        ttk.Entry(source, textvariable=self.base_path_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(source, text="Выбрать...", command=self._browse_base_path).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(source, text="По умолчанию", command=self._use_default_base).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(source, text="Обновить всё", command=self.refresh_all).grid(row=0, column=4)

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True, pady=(10, 0))

        geometry_tab_host, self.geometry_tab = create_scrollable_tab(self.notebook, padding=10)
        cylinder_tab_host, self.cylinder_tab = create_scrollable_tab(self.notebook, padding=10)
        spring_tab_host, self.spring_tab = create_scrollable_tab(self.notebook, padding=10)
        guide_tab_host, self.guide_tab = create_scrollable_tab(self.notebook, padding=10)
        self.notebook.add(geometry_tab_host, text="Подвеска")
        self.notebook.add(cylinder_tab_host, text="Цилиндры")
        self.notebook.add(spring_tab_host, text="Пружины")
        self.notebook.add(guide_tab_host, text="Параметры")

        self._build_geometry_tab()
        self._build_cylinder_tab(family_names=family_names)
        self._build_spring_tab(family_names=family_names)
        self._build_guide_tab()

        footer = build_status_strip(outer, primary_var=self.status_var, reserve_columns=1)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Button(footer, text="Обновить активную вкладку", command=self._refresh_active_tab).grid(row=0, column=1, sticky="e", padx=(12, 0))

        if self._owns_root:
            self.root.protocol("WM_DELETE_WINDOW", self._request_close)

    def _build_geometry_tab(self) -> None:
        controls = ttk.Frame(self.geometry_tab)
        controls.pack(fill="x", expand=False)
        ttk.Label(controls, text="dw min, мм").pack(side="left")
        ttk.Spinbox(
            controls,
            textvariable=self.dw_min_var,
            from_=-300.0,
            to=0.0,
            increment=5.0,
            width=10,
        ).pack(side="left", padx=(6, 12))
        ttk.Label(controls, text="dw max, мм").pack(side="left")
        ttk.Spinbox(
            controls,
            textvariable=self.dw_max_var,
            from_=0.0,
            to=300.0,
            increment=5.0,
            width=10,
        ).pack(side="left", padx=(6, 12))
        ttk.Button(controls, text="Обновить геометрию", command=self._refresh_geometry_tab).pack(side="left")

        ttk.Label(
            self.geometry_tab,
            textvariable=self.geometry_summary_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        self.geometry_tree = self._build_tree(
            self.geometry_tab,
            columns=(
                ("family", "Семейство", 160, "w"),
                ("stroke", "Ход, мм", 90, "e"),
                ("rebound", "Δшток rebound, мм", 120, "e"),
                ("static", "Δшток static, мм", 110, "e"),
                ("bump", "Δшток bump, мм", 110, "e"),
                ("mr_mid", "MR @ 0", 90, "e"),
                ("mr_peak", "MR peak", 90, "e"),
                ("usage", "Исп. хода, %", 100, "e"),
                ("notes", "Замечания", 220, "w"),
            ),
            height=14,
        )

        component_fit_frame = ttk.LabelFrame(
            self.geometry_tab,
            text="Сквозная совместимость компонентов по семействам",
            padding=8,
        )
        component_fit_frame.pack(fill="both", expand=False, pady=(10, 0))
        ttk.Label(
            component_fit_frame,
            textvariable=self.component_fit_summary_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self.component_fit_tree = self._build_tree(
            component_fit_frame,
            columns=(
                ("family", "Семейство", 150, "w"),
                ("status", "Статус", 80, "w"),
                ("usage", "Исп. хода, %", 100, "e"),
                ("mr", "MR peak", 90, "e"),
                ("stroke", "Текущий stroke, мм", 120, "e"),
                ("cyl_od", "Cylinder OD, мм", 110, "e"),
                ("spring_id", "Spring ID, мм", 110, "e"),
                ("clearance", "ID-OD, мм", 90, "e"),
                ("catalog", "Top Camozzi", 210, "w"),
                ("catalog_stroke", "Stroke rec., мм", 110, "e"),
                ("dnet", "ΔFnet rec, Н", 110, "e"),
                ("bias", "Bias rec", 90, "w"),
                ("bind", "Δbind, мм", 90, "e"),
                ("bind_target", "Target, мм", 90, "e"),
                ("action", "Следующее действие", 320, "w"),
            ),
            height=5,
        )

    def _build_cylinder_tab(self, *, family_names: tuple[str, ...]) -> None:
        filters = ttk.Frame(self.cylinder_tab)
        filters.pack(fill="x", expand=False)
        ttk.Label(filters, text="Семейство").pack(side="left")
        family_picker = ttk.Combobox(
            filters,
            textvariable=self.cylinder_family_var,
            values=family_names,
            state="readonly",
            width=16,
        )
        family_picker.pack(side="left", padx=(6, 12))
        family_picker.bind("<<ComboboxSelected>>", lambda _event: self._refresh_cylinder_tab())

        ttk.Label(filters, text="Вариант").pack(side="left")
        self.cylinder_variant_picker = ttk.Combobox(
            filters,
            textvariable=self.cylinder_variant_var,
            state="readonly",
            width=20,
        )
        self.cylinder_variant_picker.pack(side="left", padx=(6, 12))

        ttk.Label(filters, text="Pressure, bar(g)").pack(side="left")
        ttk.Spinbox(
            filters,
            textvariable=self.cylinder_pressure_var,
            from_=0.0,
            to=16.0,
            increment=0.5,
            width=10,
        ).pack(side="left", padx=(6, 12))

        ttk.Label(filters, text="Поиск").pack(side="left")
        ttk.Entry(filters, textvariable=self.cylinder_search_var, width=30).pack(side="left", padx=(6, 12))
        ttk.Button(filters, text="Обновить каталог", command=self._refresh_cylinder_tab).pack(side="left")

        ttk.Label(
            self.cylinder_tab,
            textvariable=self.cylinder_context_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        current_frame = ttk.LabelFrame(self.cylinder_tab, text="Текущий комплект цилиндров из base", padding=8)
        current_frame.pack(fill="both", expand=False)
        self.current_cylinder_tree = self._build_tree(
            current_frame,
            columns=(
                ("family", "Семейство", 150, "w"),
                ("bore", "Bore, мм", 90, "e"),
                ("rod", "Rod, мм", 90, "e"),
                ("stroke", "Stroke, мм", 90, "e"),
                ("od", "OD, мм", 90, "e"),
                ("body", "Body, мм", 90, "e"),
                ("body_need", "Stroke+dead, мм", 110, "e"),
                ("body_gap", "Δbody, мм", 90, "e"),
                ("cap", "Acap, см²", 90, "e"),
                ("ann", "Arod-side, см²", 110, "e"),
            ),
            height=5,
        )
        self.current_cylinder_tree.bind("<<TreeviewSelect>>", self._on_current_cylinder_selected)

        precharge_frame = ttk.LabelFrame(
            self.cylinder_tab,
            text="Текущий precharge / force bias из base",
            padding=8,
        )
        precharge_frame.pack(fill="both", expand=False, pady=(10, 0))
        ttk.Label(
            precharge_frame,
            textvariable=self.cylinder_precharge_summary_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self.current_cylinder_precharge_tree = self._build_tree(
            precharge_frame,
            columns=(
                ("family", "Семейство", 150, "w"),
                ("pcap_abs", "Pcap abs, кПа", 100, "e"),
                ("prod_abs", "Prod abs, кПа", 100, "e"),
                ("pcap_g", "Pcap, bar(g)", 100, "e"),
                ("prod_g", "Prod, bar(g)", 100, "e"),
                ("f_cap", "Fcap, Н", 100, "e"),
                ("f_rod", "Frod, Н", 100, "e"),
                ("f_net", "Fnet, Н", 100, "e"),
                ("bias", "Bias", 90, "w"),
                ("notes", "Замечания", 220, "w"),
            ),
            height=5,
        )

        recommendation_frame = ttk.LabelFrame(
            self.cylinder_tab,
            text="Рекомендованные каталожные варианты для текущего family",
            padding=8,
        )
        recommendation_frame.pack(fill="both", expand=False, pady=(10, 0))
        self.recommendation_tree = self._build_tree(
            recommendation_frame,
            columns=(
                ("variant", "Вариант", 160, "w"),
                ("bore", "Bore, мм", 90, "e"),
                ("rod", "Rod, мм", 90, "e"),
                ("stroke", "Stroke rec., мм", 110, "e"),
                ("db", "Δbore, мм", 90, "e"),
                ("dr", "Δrod, мм", 90, "e"),
                ("ds", "Δstroke, мм", 100, "e"),
                ("dnet", "ΔFnet, Н", 100, "e"),
                ("bias", "Bias", 80, "w"),
                ("score", "Score", 90, "e"),
                ("notes", "Причина", 260, "w"),
            ),
            height=6,
        )
        self.recommendation_tree.bind("<<TreeviewSelect>>", self._on_recommendation_selected)

        ttk.Label(
            self.cylinder_tab,
            textvariable=self.cylinder_recommendation_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        catalog_frame = ttk.LabelFrame(self.cylinder_tab, text="Camozzi catalog + force estimate", padding=8)
        catalog_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.catalog_tree = self._build_tree(
            catalog_frame,
            columns=(
                ("variant", "Вариант", 160, "w"),
                ("bore", "Bore, мм", 90, "e"),
                ("rod", "Rod, мм", 90, "e"),
                ("port", "Port", 90, "w"),
                ("rod_thread", "Rod thread", 110, "w"),
                ("B", "B, мм", 80, "e"),
                ("E", "E, мм", 80, "e"),
                ("TG", "TG, мм", 80, "e"),
                ("cap", "Acap, см²", 90, "e"),
                ("ann", "Arod-side, см²", 110, "e"),
                ("f_cap", "Fcap, Н", 100, "e"),
                ("f_rod", "Frod, Н", 100, "e"),
            ),
            height=12,
        )
        self.catalog_tree.bind("<<TreeviewSelect>>", self._on_catalog_selected)

        ttk.Label(
            self.cylinder_tab,
            textvariable=self.cylinder_choice_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_spring_tab(self, *, family_names: tuple[str, ...]) -> None:
        current_frame = ttk.LabelFrame(self.spring_tab, text="Текущая spring geometry из base", padding=8)
        current_frame.pack(fill="both", expand=False)
        self.current_spring_tree = self._build_tree(
            current_frame,
            columns=(
                ("family", "Семейство", 150, "w"),
                ("wire", "d, мм", 80, "e"),
                ("mean", "Dmean, мм", 100, "e"),
                ("inner", "ID, мм", 80, "e"),
                ("outer", "OD, мм", 80, "e"),
                ("g", "G, ГПа", 80, "e"),
                ("k", "k, Н/мм", 90, "e"),
                ("solid", "Lsolid, мм", 90, "e"),
                ("reserve", "Δbind, мм", 90, "e"),
                ("target", "Reserve min, мм", 110, "e"),
            ),
            height=5,
        )
        self.current_spring_tree.bind("<<TreeviewSelect>>", self._on_current_spring_selected)

        install_frame = ttk.LabelFrame(self.spring_tab, text="Текущий spring install contract из base", padding=8)
        install_frame.pack(fill="both", expand=False, pady=(10, 0))
        ttk.Label(
            install_frame,
            textvariable=self.spring_install_summary_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self.current_spring_install_tree = self._build_tree(
            install_frame,
            columns=(
                ("family", "Семейство", 150, "w"),
                ("free", "Lfree, мм", 90, "e"),
                ("free_pitch", "Lfree(pitch), мм", 110, "e"),
                ("free_gap", "ΔLfree, мм", 90, "e"),
                ("top_gap", "Top gap, мм", 90, "e"),
                ("rebound", "Rebound min, мм", 110, "e"),
                ("bind_target", "Δbind min, мм", 100, "e"),
            ),
            height=5,
        )

        calculator = ttk.LabelFrame(self.spring_tab, text="Spring geometry / coil-bind calculator", padding=10)
        calculator.pack(fill="x", expand=False, pady=(10, 0))
        for idx in range(4):
            calculator.columnconfigure(idx, weight=1 if idx % 2 == 1 else 0)

        ttk.Label(calculator, text="Семейство").grid(row=0, column=0, sticky="w")
        family_picker = ttk.Combobox(
            calculator,
            textvariable=self.spring_family_var,
            values=family_names,
            state="readonly",
            width=18,
        )
        family_picker.grid(row=0, column=1, sticky="ew", padx=(6, 16))
        family_picker.bind("<<ComboboxSelected>>", lambda _event: self._refresh_spring_reference())
        ttk.Button(calculator, text="Загрузить из base", command=self._load_selected_spring_family_from_base).grid(
            row=0,
            column=2,
            sticky="w",
        )
        ttk.Button(calculator, text="Пересчитать", command=self._refresh_spring_reference).grid(
            row=0,
            column=3,
            sticky="e",
        )

        ttk.Label(calculator, textvariable=self.spring_static_mode_var, wraplength=1180, justify="left").grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(8, 10),
        )

        fields = (
            ("d wire, мм", self.spring_wire_var, 2, 0, 1.0, 30.0, 0.5),
            ("D mean, мм", self.spring_mean_diameter_var, 2, 2, 10.0, 240.0, 1.0),
            ("N active", self.spring_active_turns_var, 3, 0, 1.0, 30.0, 1.0),
            ("N total", self.spring_total_turns_var, 3, 2, 1.0, 40.0, 1.0),
            ("Pitch, мм", self.spring_pitch_var, 4, 0, 0.0, 60.0, 0.5),
            ("G, ГПа", self.spring_g_var, 4, 2, 1.0, 120.0, 1.0),
            ("Fmax, Н", self.spring_force_var, 5, 0, 0.0, 200000.0, 500.0),
        )
        for label, variable, row, column, min_value, max_value, step in fields:
            ttk.Label(calculator, text=label).grid(row=row, column=column, sticky="w", pady=2)
            ttk.Spinbox(
                calculator,
                textvariable=variable,
                from_=min_value,
                to=max_value,
                increment=step,
                width=14,
            ).grid(row=row, column=column + 1, sticky="ew", padx=(6, 16), pady=2)

        ttk.Label(
            self.spring_tab,
            textvariable=self.spring_summary_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_guide_tab(self) -> None:
        filters = ttk.Frame(self.guide_tab)
        filters.pack(fill="x", expand=False)
        ttk.Label(filters, text="Search").pack(side="left")
        ttk.Entry(filters, textvariable=self.guide_query_var, width=40).pack(side="left", padx=(6, 12))
        ttk.Button(filters, text="Найти", command=self._refresh_parameter_guide).pack(side="left", padx=(0, 6))
        ttk.Button(filters, text="Показать reference set", command=self._clear_guide_query).pack(side="left")

        ttk.Label(
            self.guide_tab,
            textvariable=self.guide_summary_var,
            wraplength=1440,
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        self.guide_tree = self._build_tree(
            self.guide_tab,
            columns=(
                ("label", "Параметр", 220, "w"),
                ("unit", "Ед.", 90, "w"),
                ("section", "Раздел", 130, "w"),
                ("current", "Текущее", 140, "w"),
                ("key", "Ключ", 240, "w"),
                ("description", "Описание", 560, "w"),
            ),
            height=16,
        )

    def _build_tree(
        self,
        parent: tk.Misc,
        *,
        columns: tuple[tuple[str, str, int, str], ...],
        height: int,
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            frame,
            columns=tuple(name for name, _title, _width, _anchor in columns),
            show="headings",
            height=height,
        )
        for name, title, width, anchor in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, anchor=anchor, stretch=True)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        return tree

    def _browse_base_path(self) -> None:
        current_path = self.runtime.resolve_base_path(self.base_path_var.get())
        initial_dir = current_path.parent if current_path.parent.exists() else current_path
        path = filedialog.askopenfilename(
            title="Выбрать базовый JSON для справочного центра",
            initialdir=str(initial_dir),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self.base_path_var.set(path)
        self.refresh_all()

    def _use_default_base(self) -> None:
        self.base_path_var.set(str(self.runtime.base_path))
        self.refresh_all()

    def _fmt(self, value: float, digits: int = 1) -> str:
        return f"{float(value):.{digits}f}" if math.isfinite(value) else "—"

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def _base_path(self) -> str:
        return str(self.base_path_var.get() or "").strip()

    def refresh_all(self) -> None:
        self._refresh_geometry_tab()
        self._refresh_cylinder_tab()
        self._refresh_spring_tab()
        self._refresh_parameter_guide()
        self.status_var.set(
            "Справочный центр обновлён. Источник: " + self.runtime.describe_base_source(self._base_path())
        )

    def _refresh_active_tab(self) -> None:
        current = self.notebook.index(self.notebook.select())
        if current == 0:
            self._refresh_geometry_tab()
        elif current == 1:
            self._refresh_cylinder_tab()
        elif current == 2:
            self._refresh_spring_tab()
        else:
            self._refresh_parameter_guide()

    def _refresh_geometry_tab(self) -> None:
        snapshot = self.runtime.geometry_snapshot(
            self._base_path(),
            dw_min_mm=float(self.dw_min_var.get()),
            dw_max_mm=float(self.dw_max_var.get()),
        )
        self.geometry_summary_var.set(
            " | ".join(
                (
                    self.runtime.describe_base_source(self._base_path()),
                    f"база={self._fmt(snapshot.wheelbase_mm, 1)} мм",
                    f"колея={self._fmt(snapshot.track_mm, 1)} мм",
                    f"кинематика={snapshot.mechanics_mode or '—'}",
                    f"колесо_координата={snapshot.wheel_coord_mode or '—'}",
                    f"dw=[{self._fmt(snapshot.dw_min_mm, 0)} .. {self._fmt(snapshot.dw_max_mm, 0)}] мм",
                )
            )
        )
        self._clear_tree(self.geometry_tree)
        for idx, row in enumerate(snapshot.families):
            self.geometry_tree.insert(
                "",
                "end",
                iid=f"geo_{idx}",
                values=(
                    row.family,
                    self._fmt(row.stroke_mm, 1),
                    self._fmt(row.rod_rebound_mm, 1),
                    self._fmt(row.rod_static_mm, 1),
                    self._fmt(row.rod_bump_mm, 1),
                    self._fmt(row.motion_ratio_mid, 3),
                    self._fmt(row.motion_ratio_peak, 3),
                    self._fmt(row.stroke_usage_pct, 1),
                    ", ".join(row.notes) if row.notes else "ok",
                ),
            )

        component_fit_rows = self.runtime.component_fit_rows(
            self._base_path(),
            dw_min_mm=float(self.dw_min_var.get()),
            dw_max_mm=float(self.dw_max_var.get()),
        )
        self._component_fit_rows_by_family = {row.family: row for row in component_fit_rows}
        warn_count = sum(1 for row in component_fit_rows if row.status == "warn")
        self.component_fit_summary_var.set(
            f"Сводка помогает связать geometry, текущий cylinder family, посадку cylinder OD -> spring ID, "
            f"ближайший Camozzi match, его precharge-bias shift и coil-bind reserve. "
            f"Семейств с предупреждениями: {warn_count} из {len(component_fit_rows)}."
        )
        self._clear_tree(self.component_fit_tree)
        for idx, row in enumerate(component_fit_rows):
            self.component_fit_tree.insert(
                "",
                "end",
                iid=f"fit_{idx}",
                values=(
                    row.family,
                    row.status,
                    self._fmt(row.stroke_usage_pct, 1),
                    self._fmt(row.motion_ratio_peak, 3),
                    self._fmt(row.current_stroke_mm, 1),
                    self._fmt(row.cylinder_outer_diameter_mm, 1),
                    self._fmt(row.spring_inner_diameter_mm, 1),
                    self._fmt(row.spring_to_cylinder_clearance_mm, 1),
                    row.recommended_catalog_label,
                    self._fmt(row.recommended_stroke_mm, 0),
                    self._fmt(row.recommended_net_force_delta_N, 0),
                    row.recommended_bias_direction,
                    self._fmt(row.spring_bind_margin_mm, 1),
                    self._fmt(row.spring_bind_target_mm, 1),
                    row.action_summary,
                ),
            )

    def _refresh_cylinder_tab(self) -> None:
        current_rows = self.runtime.current_cylinder_rows(self._base_path())
        self._current_cylinder_rows_by_family = {row.family: row for row in current_rows}
        package_rows = self.runtime.current_cylinder_package_rows(self._base_path())
        self._current_cylinder_package_rows_by_family = {row.family: row for row in package_rows}
        self._clear_tree(self.current_cylinder_tree)
        selected_current_iid = None
        for idx, row in enumerate(current_rows):
            package = self._current_cylinder_package_rows_by_family.get(row.family)
            iid = f"curr_cyl_{idx}"
            self.current_cylinder_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row.family,
                    self._fmt(row.bore_mm, 1),
                    self._fmt(row.rod_mm, 1),
                    self._fmt(row.stroke_mm, 1),
                    self._fmt(package.outer_diameter_mm, 1) if package is not None else "—",
                    self._fmt(package.body_length_mm, 1) if package is not None else "—",
                    self._fmt(package.expected_body_length_mm, 1) if package is not None else "—",
                    self._fmt(package.body_length_gap_mm, 1) if package is not None else "—",
                    self._fmt(row.cap_area_cm2, 3),
                    self._fmt(row.annulus_area_cm2, 3),
                ),
            )
            if row.family == self.cylinder_family_var.get():
                selected_current_iid = iid
        if selected_current_iid:
            self.current_cylinder_tree.selection_set(selected_current_iid)

        precharge_rows = self.runtime.current_cylinder_precharge_rows(self._base_path())
        self._current_cylinder_precharge_rows_by_family = {row.family: row for row in precharge_rows}
        finite_precharge_count = sum(
            1
            for row in precharge_rows
            if math.isfinite(row.cap_precharge_abs_kpa) or math.isfinite(row.rod_precharge_abs_kpa)
        )
        self.cylinder_precharge_summary_var.set(
            "Сводка переводит абсолютный precharge из family-contract в bar(g) относительно атмосферы "
            "и оценивает Fcap/Frod/Fnet по текущим bore/rod. "
            f"Семейств с заданным precharge: {finite_precharge_count} из {len(precharge_rows)}."
        )
        self._clear_tree(self.current_cylinder_precharge_tree)
        for idx, row in enumerate(precharge_rows):
            self.current_cylinder_precharge_tree.insert(
                "",
                "end",
                iid=f"curr_cyl_precharge_{idx}",
                values=(
                    row.family,
                    self._fmt(row.cap_precharge_abs_kpa, 1),
                    self._fmt(row.rod_precharge_abs_kpa, 1),
                    self._fmt(row.cap_precharge_bar_g, 2),
                    self._fmt(row.rod_precharge_bar_g, 2),
                    self._fmt(row.cap_force_N, 0),
                    self._fmt(row.rod_force_N, 0),
                    self._fmt(row.net_force_N, 0),
                    row.bias_direction,
                    ", ".join(row.notes) if row.notes else "ok",
                ),
            )

        variant_values = ("Все варианты", *self.runtime.catalog_variant_labels())
        self.cylinder_variant_picker.configure(values=variant_values)
        if self.cylinder_variant_var.get() not in variant_values:
            self.cylinder_variant_var.set("Все варианты")

        self.cylinder_context_var.set(
            "Текущий family context берётся из base и показан сверху. "
            "В current-table теперь виден и package contract: OD, body length и согласованность body со stroke+dead lengths. "
            "Сначала показывается precharge->force bias summary для live base, "
            "Ниже показывается shortlist ближайших Camozzi-вариантов по bore/rod/stroke и по смещению current precharge bias, "
            "а полный каталог справа фильтруется по варианту и поиску, показывает raw Camozzi dims B/E/TG "
            "и считает усилия как p*A."
        )

        recommendations = self.runtime.cylinder_match_recommendations(
            self.cylinder_family_var.get(),
            raw_path=self._base_path(),
            variant_label=self.cylinder_variant_var.get(),
            search_query=self.cylinder_search_var.get(),
            limit=5,
        )
        self._recommendations_by_iid.clear()
        self._clear_tree(self.recommendation_tree)
        top_recommendation_iid = None
        for idx, recommendation in enumerate(recommendations):
            iid = f"rec_{idx}"
            self.recommendation_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    recommendation.variant_label,
                    recommendation.bore_mm,
                    recommendation.rod_mm,
                    self._fmt(recommendation.recommended_stroke_mm, 0),
                    self._fmt(recommendation.bore_delta_mm, 1),
                    self._fmt(recommendation.rod_delta_mm, 1),
                    self._fmt(recommendation.stroke_delta_mm, 1),
                    self._fmt(recommendation.net_force_delta_N, 0),
                    recommendation.bias_direction,
                    self._fmt(recommendation.score, 1),
                    ", ".join(recommendation.notes),
                ),
            )
            self._recommendations_by_iid[iid] = recommendation
            if top_recommendation_iid is None:
                top_recommendation_iid = iid
        if top_recommendation_iid:
            self.recommendation_tree.selection_set(top_recommendation_iid)

        rows = self.runtime.cylinder_catalog_rows(
            variant_label=self.cylinder_variant_var.get(),
            search_query=self.cylinder_search_var.get(),
        )
        self._catalog_rows_by_iid.clear()
        self._clear_tree(self.catalog_tree)
        selected_iid = None
        for idx, row in enumerate(rows):
            iid = f"cat_{idx}"
            estimate = self.runtime.cylinder_pressure_summary(row, float(self.cylinder_pressure_var.get()))
            self.catalog_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row.variant_label,
                    row.bore_mm,
                    row.rod_mm,
                    row.port_thread or "—",
                    row.rod_thread or "—",
                    self._fmt(row.B_mm, 1),
                    self._fmt(row.E_mm, 1),
                    self._fmt(row.TG_mm, 1),
                    self._fmt(row.cap_area_cm2, 3),
                    self._fmt(row.annulus_area_cm2, 3),
                    self._fmt(estimate.cap_force_N, 0),
                    self._fmt(estimate.rod_force_N, 0),
                ),
            )
            self._catalog_rows_by_iid[iid] = row
            if selected_iid is None:
                selected_iid = iid
        if selected_iid:
            self.catalog_tree.selection_set(selected_iid)
            self.catalog_tree.focus(selected_iid)
        self._refresh_cylinder_selection_summary()

    def _refresh_cylinder_selection_summary(self) -> None:
        selection = self.catalog_tree.selection()
        row = self._catalog_rows_by_iid.get(selection[0]) if selection else None
        current = self._current_cylinder_rows_by_family.get(self.cylinder_family_var.get())
        current_package = self._current_cylinder_package_rows_by_family.get(self.cylinder_family_var.get())
        current_precharge = self._current_cylinder_precharge_rows_by_family.get(self.cylinder_family_var.get())
        if row is None:
            self.cylinder_choice_var.set("Каталог пуст по текущему фильтру. Ослабьте variant/search.")
            self.cylinder_recommendation_var.set("Рекомендации недоступны, пока каталог пуст по текущим фильтрам.")
            return

        recommendation_selection = self.recommendation_tree.selection()
        recommendation = (
            self._recommendations_by_iid.get(recommendation_selection[0])
            if recommendation_selection
            else None
        )
        if recommendation is not None:
            recommendation_line = (
                f"Top shortlist для {recommendation.family}: {recommendation.variant_label} "
                f"{recommendation.bore_mm}/{recommendation.rod_mm} мм, "
                f"рекомендованный stroke={self._fmt(recommendation.recommended_stroke_mm, 0)} мм, "
                f"Δbore={self._fmt(recommendation.bore_delta_mm, 1)} мм, "
                f"Δrod={self._fmt(recommendation.rod_delta_mm, 1)} мм, "
                f"Δstroke={self._fmt(recommendation.stroke_delta_mm, 1)} мм, "
                f"score={self._fmt(recommendation.score, 1)}."
            )
            if math.isfinite(recommendation.net_force_N):
                recommendation_line += (
                    f" Fnet@current-precharge≈{self._fmt(recommendation.net_force_N, 0)} Н, "
                    f"ΔFnet≈{self._fmt(recommendation.net_force_delta_N, 0)} Н, "
                    f"bias={recommendation.bias_direction}."
                )
            recommendation_line += f" {', '.join(recommendation.notes)}."
            self.cylinder_recommendation_var.set(recommendation_line)
        else:
            self.cylinder_recommendation_var.set(
                "Рекомендации не найдены под текущий family/filter; проверьте variant/search."
            )

        estimate = self.runtime.cylinder_pressure_summary(row, float(self.cylinder_pressure_var.get()))
        lines = [
            f"Выбран каталог: {row.variant_label} | bore={row.bore_mm} мм | rod={row.rod_mm} мм | "
            f"port={row.port_thread or '—'} | rod-thread={row.rod_thread or '—'}.",
            f"Camozzi ref dims: B≈{self._fmt(row.B_mm, 1)} мм, E≈{self._fmt(row.E_mm, 1)} мм, TG≈{self._fmt(row.TG_mm, 1)} мм.",
            f"При {self._fmt(float(self.cylinder_pressure_var.get()), 1)} bar(g): "
            f"Fcap≈{self._fmt(estimate.cap_force_N, 0)} Н ({self._fmt(estimate.cap_force_kgf, 1)} кгс), "
            f"Frod≈{self._fmt(estimate.rod_force_N, 0)} Н ({self._fmt(estimate.rod_force_kgf, 1)} кгс).",
        ]
        if current is not None and current.cap_area_cm2 > 0.0:
            cap_ratio = row.cap_area_cm2 / current.cap_area_cm2
            ann_ratio = (
                row.annulus_area_cm2 / current.annulus_area_cm2
                if current.annulus_area_cm2 > 0.0
                else float("nan")
            )
            lines.append(
                f"Текущее family {current.family}: bore={self._fmt(current.bore_mm, 1)} мм, "
                f"rod={self._fmt(current.rod_mm, 1)} мм, stroke={self._fmt(current.stroke_mm, 1)} мм. "
                f"Относительно base: Acap x{self._fmt(cap_ratio, 2)}, Arod-side x{self._fmt(ann_ratio, 2)}."
            )
            lines.append(
                "Каталог помогает выбрать реальный bore/rod; stroke и интеграция в current geometry остаются "
                "отдельным инженерным решением и берутся из base/kinematics."
            )
        else:
            lines.append(
                "Текущий family-context в base нечитабелен, поэтому сравнение с live setup пропущено."
            )
        if current_package is not None:
            lines.append(
                f"Package contract: OD≈{self._fmt(current_package.outer_diameter_mm, 1)} мм, "
                f"body≈{self._fmt(current_package.body_length_mm, 1)} мм, "
                f"stroke+dead≈{self._fmt(current_package.expected_body_length_mm, 1)} мм, "
                f"Δbody≈{self._fmt(current_package.body_length_gap_mm, 1)} мм, "
                f"dead cap≈{self._fmt(current_package.dead_cap_length_mm, 1)} мм, "
                f"dead rod≈{self._fmt(current_package.dead_rod_length_mm, 1)} мм, "
                f"dead height≈{self._fmt(current_package.dead_height_mm, 1)} мм. "
                f"{', '.join(current_package.notes) if current_package.notes else 'package ок'}."
            )
        if current_precharge is not None:
            if math.isfinite(current_precharge.net_force_N):
                catalog_bias = build_cylinder_force_bias_estimate(
                    row,
                    cap_pressure_bar_gauge=float(current_precharge.cap_precharge_bar_g),
                    rod_pressure_bar_gauge=float(current_precharge.rod_precharge_bar_g),
                    clamp_negative=False,
                )
                lines.append(
                    f"Current precharge bias для {current_precharge.family}: "
                    f"Pcap≈{self._fmt(current_precharge.cap_precharge_bar_g, 2)} bar(g), "
                    f"Prod≈{self._fmt(current_precharge.rod_precharge_bar_g, 2)} bar(g), "
                    f"Fnet≈{self._fmt(current_precharge.net_force_N, 0)} Н "
                    f"({self._fmt(current_precharge.net_force_kgf, 1)} кгс), режим={current_precharge.bias_direction}."
                )
                lines.append(
                    f"Если выбранный каталог запитать текущим family precharge: "
                    f"Fcap≈{self._fmt(catalog_bias.cap_force_N, 0)} Н, "
                    f"Frod≈{self._fmt(catalog_bias.rod_force_N, 0)} Н, "
                    f"Fnet≈{self._fmt(catalog_bias.net_force_N, 0)} Н "
                    f"({self._fmt(catalog_bias.net_force_kgf, 1)} кгс), режим={catalog_bias.bias_direction}, "
                    f"Δк текущему bias≈{self._fmt(catalog_bias.net_force_N - current_precharge.net_force_N, 0)} Н."
                )
            else:
                lines.append(
                    "Для текущего family в base пока нет полного CAP/ROD precharge, "
                    "поэтому live force bias не оценен."
                )
        self.cylinder_choice_var.set(" ".join(lines))

    def _refresh_spring_tab(self) -> None:
        snapshot = self.runtime.current_spring_snapshot(self._base_path())
        self._current_spring_rows_by_family = {row.family: row for row in snapshot.families}
        self.spring_static_mode_var.set(
            f"Static mode: {snapshot.static_mode or '—'}. "
            + spring_static_mode_description(snapshot.static_mode)
        )

        self._clear_tree(self.current_spring_tree)
        selected_iid = None
        for idx, row in enumerate(snapshot.families):
            iid = f"curr_spring_{idx}"
            self.current_spring_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row.family,
                    self._fmt(row.wire_mm, 1),
                    self._fmt(row.mean_diameter_mm, 1),
                    self._fmt(row.inner_diameter_mm, 1),
                    self._fmt(row.outer_diameter_mm, 1),
                    self._fmt(row.shear_modulus_GPa, 1),
                    self._fmt(row.rate_N_per_mm, 3),
                    self._fmt(row.solid_length_mm, 1),
                    self._fmt(row.bind_travel_margin_mm, 1),
                    self._fmt(row.bind_margin_target_mm, 1),
                ),
            )
            if row.family == self.spring_family_var.get():
                selected_iid = iid
        if selected_iid:
            self.current_spring_tree.selection_set(selected_iid)

        install_gap_warn_count = sum(
            1
            for row in snapshot.families
            if math.isfinite(row.free_length_pitch_gap_mm) and abs(float(row.free_length_pitch_gap_mm)) > 5.0
        )
        self.spring_install_summary_var.set(
            "Сводка показывает live spring install contract: canonical Lfree, top gap, rebound preload min "
            "и расхождение между contract Lfree и Lfree, который следует из текущего pitch. "
            f"Семейств с заметным ΔLfree: {install_gap_warn_count} из {len(snapshot.families)}."
        )
        self._clear_tree(self.current_spring_install_tree)
        for idx, row in enumerate(snapshot.families):
            self.current_spring_install_tree.insert(
                "",
                "end",
                iid=f"curr_spring_install_{idx}",
                values=(
                    row.family,
                    self._fmt(row.free_length_mm, 1),
                    self._fmt(row.free_length_from_pitch_mm, 1),
                    self._fmt(row.free_length_pitch_gap_mm, 1),
                    self._fmt(row.top_offset_mm, 1),
                    self._fmt(row.rebound_preload_min_mm, 1),
                    self._fmt(row.bind_margin_target_mm, 1),
                ),
            )

        if not self._spring_inputs_seeded:
            self._load_selected_spring_family_from_base()
            self._spring_inputs_seeded = True
            return
        self._refresh_spring_reference()

    def _load_selected_spring_family_from_base(self) -> None:
        row = self._current_spring_rows_by_family.get(self.spring_family_var.get())
        if row is None:
            self._refresh_spring_reference()
            return
        if math.isfinite(row.wire_mm) and row.wire_mm > 0.0:
            self.spring_wire_var.set(row.wire_mm)
        if math.isfinite(row.mean_diameter_mm) and row.mean_diameter_mm > 0.0:
            self.spring_mean_diameter_var.set(row.mean_diameter_mm)
        if math.isfinite(row.active_turns) and row.active_turns > 0.0:
            self.spring_active_turns_var.set(row.active_turns)
        if math.isfinite(row.total_turns) and row.total_turns > 0.0:
            self.spring_total_turns_var.set(row.total_turns)
        if math.isfinite(row.pitch_mm) and row.pitch_mm >= 0.0:
            self.spring_pitch_var.set(row.pitch_mm)
        if math.isfinite(row.shear_modulus_GPa) and row.shear_modulus_GPa > 0.0:
            self.spring_g_var.set(row.shear_modulus_GPa)
        self._refresh_spring_reference()

    def _refresh_spring_reference(self) -> None:
        geometry = build_spring_geometry_reference(
            d_wire_m=float(self.spring_wire_var.get()) / 1000.0,
            D_mean_m=float(self.spring_mean_diameter_var.get()) / 1000.0,
            N_active=float(self.spring_active_turns_var.get()),
            N_total=float(self.spring_total_turns_var.get()),
            pitch_m=float(self.spring_pitch_var.get()) / 1000.0,
            G_Pa=float(self.spring_g_var.get()) * 1.0e9,
            F_max_N=float(self.spring_force_var.get()),
        )
        current = self._current_spring_rows_by_family.get(self.spring_family_var.get())
        current_fit = self._component_fit_rows_by_family.get(self.spring_family_var.get())
        calc_inner_mm = (
            (float(geometry.D_mean_m) - float(geometry.d_wire_m)) * 1000.0
            if float(geometry.D_mean_m) > float(geometry.d_wire_m) > 0.0
            else float("nan")
        )
        calc_outer_mm = (
            (float(geometry.D_mean_m) + float(geometry.d_wire_m)) * 1000.0
            if float(geometry.D_mean_m) > 0.0 and float(geometry.d_wire_m) > 0.0
            else float("nan")
        )
        lines = [
            f"Калькулятор для {self.spring_family_var.get()}: "
            f"k≈{self._fmt(geometry.rate_N_per_mm, 3)} Н/мм, "
            f"Lsolid≈{self._fmt(geometry.solid_length_m * 1000.0, 1)} мм, "
            f"Lfree(pitch)≈{self._fmt(geometry.free_length_from_pitch_m * 1000.0, 1)} мм, "
            f"Δbind≈{self._fmt(geometry.bind_travel_margin_m * 1000.0, 1)} мм, "
            f"ID≈{self._fmt(calc_inner_mm, 1)} мм, "
            f"OD≈{self._fmt(calc_outer_mm, 1)} мм, "
            f"tau_max≈{self._fmt(geometry.max_shear_stress_Pa / 1.0e6, 1)} МПа, "
            f"C≈{self._fmt(geometry.spring_index, 2)}."
        ]
        if current is not None:
            lines.append(
                f"Текущее base-семейство: k≈{self._fmt(current.rate_N_per_mm, 3)} Н/мм, "
                f"Lfree≈{self._fmt(current.free_length_mm, 1)} мм, "
                f"Lsolid≈{self._fmt(current.solid_length_mm, 1)} мм, "
                f"Δbind≈{self._fmt(current.bind_travel_margin_mm, 1)} мм, "
                f"ID≈{self._fmt(current.inner_diameter_mm, 1)} мм, "
                f"OD≈{self._fmt(current.outer_diameter_mm, 1)} мм, "
                f"top gap≈{self._fmt(current.top_offset_mm, 1)} мм, "
                f"rebound min≈{self._fmt(current.rebound_preload_min_mm, 1)} мм, "
                f"reserve min≈{self._fmt(current.bind_margin_target_mm, 1)} мм."
            )
            if math.isfinite(current.free_length_pitch_gap_mm):
                lines.append(
                    f"Согласование Lfree с pitch: contract {'выше' if current.free_length_pitch_gap_mm >= 0.0 else 'ниже'} "
                    f"pitch-derived длины на {self._fmt(abs(current.free_length_pitch_gap_mm), 1)} мм."
                )
        if current_fit is not None:
            if math.isfinite(current_fit.spring_to_cylinder_clearance_mm):
                lines.append(
                    f"Текущая посадка по диаметрам: cylinder OD≈{self._fmt(current_fit.cylinder_outer_diameter_mm, 1)} мм, "
                    f"spring ID≈{self._fmt(current_fit.spring_inner_diameter_mm, 1)} мм, "
                    f"clearance≈{self._fmt(current_fit.spring_to_cylinder_clearance_mm, 1)} мм."
                )
            else:
                lines.append(
                    "Для текущего family пока не хватает данных, чтобы проверить clearance между spring ID и cylinder OD."
                )
        if math.isfinite(geometry.bind_travel_margin_m):
            reserve_gap_mm = geometry.bind_travel_margin_m * 1000.0
            if reserve_gap_mm < 0.0:
                lines.append("Геометрия невозможна: свободная длина из pitch уже меньше solid length.")
            elif current is not None and math.isfinite(current.bind_margin_target_mm):
                delta_mm = reserve_gap_mm - current.bind_margin_target_mm
                lines.append(
                    f"Сравнение с target reserve: запас {'выше' if delta_mm >= 0.0 else 'ниже'} на {self._fmt(abs(delta_mm), 1)} мм."
                )
        self.spring_summary_var.set(" ".join(lines))

    def _refresh_parameter_guide(self) -> None:
        rows = self.runtime.parameter_guide_rows(
            self.guide_query_var.get(),
            raw_path=self._base_path(),
            limit=160,
        )
        self._clear_tree(self.guide_tree)
        for idx, row in enumerate(rows):
            self.guide_tree.insert(
                "",
                "end",
                iid=f"guide_{idx}",
                values=(
                    row.label,
                    row.unit_label or "—",
                    row.section_title,
                    row.current_value_text or "—",
                    row.key,
                    row.description,
                ),
            )
        if str(self.guide_query_var.get() or "").strip():
            self.guide_summary_var.set(
                f"Найдено {len(rows)} параметров по запросу «{self.guide_query_var.get().strip()}». "
                "Справочник строится по каноническим спецификациям desktop-полей и семейным контрактам, а не по web-разметке."
            )
        else:
            self.guide_summary_var.set(
                f"Показано {len(rows)} справочных параметров из общих разделов desktop-интерфейса и семейных контрактов с текущими значениями из базового файла."
            )

    def _clear_guide_query(self) -> None:
        self.guide_query_var.set("")
        self._refresh_parameter_guide()

    def _on_catalog_selected(self, _event: object) -> None:
        self._refresh_cylinder_selection_summary()

    def _on_recommendation_selected(self, _event: object) -> None:
        selection = self.recommendation_tree.selection()
        recommendation = self._recommendations_by_iid.get(selection[0]) if selection else None
        if recommendation is None:
            self._refresh_cylinder_selection_summary()
            return
        for iid, row in self._catalog_rows_by_iid.items():
            if (
                row.variant_key == recommendation.variant_key
                and int(row.bore_mm) == int(recommendation.bore_mm)
                and int(row.rod_mm) == int(recommendation.rod_mm)
            ):
                self.catalog_tree.selection_set(iid)
                self.catalog_tree.focus(iid)
                break
        self._refresh_cylinder_selection_summary()

    def _on_current_cylinder_selected(self, _event: object) -> None:
        selection = self.current_cylinder_tree.selection()
        if not selection:
            return
        values = self.current_cylinder_tree.item(selection[0], "values")
        if values:
            self.cylinder_family_var.set(str(values[0]))
            self._refresh_cylinder_tab()

    def _on_current_spring_selected(self, _event: object) -> None:
        selection = self.current_spring_tree.selection()
        if not selection:
            return
        values = self.current_spring_tree.item(selection[0], "values")
        if values:
            self.spring_family_var.set(str(values[0]))
            self._load_selected_spring_family_from_base()

    def _request_close(self) -> None:
        self.on_host_close()
        if self._owns_root and int(self.root.winfo_exists()):
            self.root.destroy()

    def on_host_close(self) -> None:
        self._host_closed = True

    def run(self) -> None:
        if self._owns_root:
            self.root.mainloop()


def main() -> int:
    app = DesktopGeometryReferenceCenter()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
