from __future__ import annotations

from typing import Any, Callable

from pneumo_solver_ui.ui_suite_editor_shell_helpers import render_suite_card_heading


SectionRenderer = Callable[[], None]
UploadApplyFn = Callable[[str | None, str | None], None]


def render_suite_card_primary_section_intro(st: Any) -> None:
    st.markdown("#### 1. Основное")
    st.caption(
        "Сначала задайте, участвует ли сценарий в наборе, как он называется "
        "и к какому типу относится."
    )


def render_suite_card_timing_section_intro(st: Any) -> None:
    st.markdown("#### 2. Время расчета")
    st.caption(
        "Проверьте шаг интегрирования и длительность сценария. Эти параметры "
        "влияют и на устойчивость расчета, и на его стоимость."
    )


def render_suite_card_motion_section_intro(st: Any, *, title: str) -> None:
    st.markdown(f"#### {title}")
    st.caption(
        "Здесь задаются входные воздействия: дорога, скорость, ускорения "
        "и маневр, если они нужны для этого сценария."
    )


def render_suite_card_targets_section_intro(st: Any) -> None:
    st.markdown("#### 4. Цели и ограничения")
    st.caption(
        "Включайте только те целевые ограничения, которые действительно "
        "должны участвовать в штрафе и проверке сценария."
    )


def render_suite_card_draft_notice(st: Any) -> None:
    st.caption(
        "Черновик карточки хранится в состоянии интерфейса: обычное обновление страницы "
        "не должно откатывать несохранённые поля."
    )


def render_suite_csv_upload_panel(
    st: Any,
    *,
    sid: str,
    save_upload_fn: Callable[[Any, str], str | None],
) -> tuple[str | None, str | None]:
    uploaded_road_csv: str | None = None
    uploaded_axay_csv: str | None = None

    with st.expander("CSV профиля дороги / маневра (опционально)", expanded=True):
        st.caption(
            "Если нужно, загрузите CSV. Файл будет сохранен в "
            "`workspace/uploads`, а путь автоматически подставится в поля ниже."
        )
        up_road = st.file_uploader(
            "Профиль дороги (CSV)",
            type=["csv"],
            key=f"suite_road_csv_upload_{sid}",
            help=(
                "Используется в сценариях с дорожным профилем из CSV "
                "и при необходимости в других сценариях."
            ),
        )
        if up_road is not None:
            uploaded_road_csv = save_upload_fn(up_road, "road")
            if uploaded_road_csv:
                st.success(f"Профиль дороги сохранен: {uploaded_road_csv}")

        up_axay = st.file_uploader(
            "Маневр (CSV ax/ay)",
            type=["csv"],
            key=f"suite_axay_csv_upload_{sid}",
            help=(
                "Используется в сценариях с маневром из CSV "
                "и при необходимости в других сценариях."
            ),
        )
        if up_axay is not None:
            uploaded_axay_csv = save_upload_fn(up_axay, "axay")
            if uploaded_axay_csv:
                st.success(f"Маневр сохранен: {uploaded_axay_csv}")

    return uploaded_road_csv, uploaded_axay_csv


def render_app_suite_right_card_shell(
    st: Any,
    *,
    name: str,
    render_primary_section: SectionRenderer,
    render_timing_section: SectionRenderer,
    render_motion_section: SectionRenderer,
    render_targets_section: SectionRenderer,
) -> None:
    with st.container():
        render_suite_card_heading(st, name)
        render_suite_card_primary_section_intro(st)
        render_primary_section()
        render_suite_card_timing_section_intro(st)
        render_timing_section()
        render_suite_card_motion_section_intro(st, title="3. Возмущение и маневр")
        render_motion_section()
        render_suite_card_targets_section_intro(st)
        render_targets_section()


def render_heavy_suite_right_card_shell(
    st: Any,
    *,
    title: str,
    sid: str,
    save_upload_fn: Callable[[Any, str], str | None],
    apply_uploaded_paths_fn: UploadApplyFn,
    render_primary_section: SectionRenderer,
    render_timing_section: SectionRenderer,
    render_motion_section: SectionRenderer,
    render_targets_section: SectionRenderer,
) -> None:
    render_suite_card_heading(st, title)
    render_suite_card_primary_section_intro(st)
    render_primary_section()
    uploaded_road_csv, uploaded_axay_csv = render_suite_csv_upload_panel(
        st,
        sid=sid,
        save_upload_fn=save_upload_fn,
    )
    apply_uploaded_paths_fn(uploaded_road_csv, uploaded_axay_csv)
    render_suite_card_draft_notice(st)
    render_suite_card_timing_section_intro(st)
    render_timing_section()
    render_suite_card_motion_section_intro(st, title="3. Дорога и маневр")
    render_motion_section()
    render_suite_card_targets_section_intro(st)
    render_targets_section()
