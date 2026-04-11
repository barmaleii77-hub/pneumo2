from __future__ import annotations

from typing import Any


def has_packaging_snapshot(snapshot: Any) -> bool:
    return snapshot is not None and int(getattr(snapshot, "rows_with_packaging", 0) or 0) > 0


def render_packaging_snapshot_summary(
    st: Any,
    snapshot: Any,
    *,
    compact: bool = False,
    heading: str = "Сводка по геометрии узлов",
    interference_prefix: str = "В run есть признаки пересечений по геометрии узлов",
) -> bool:
    if not has_packaging_snapshot(snapshot):
        return False

    if compact:
        st.caption(
            "Геометрия узлов: "
            f"строк={int(snapshot.rows_with_packaging)}, "
            f"данных достаточно={int(snapshot.packaging_truth_ready_rows)}, "
            f"автопроверка OK={int(snapshot.packaging_verification_pass_rows)}, "
            f"служебный fallback={int(snapshot.runtime_fallback_rows)}"
        )
        if int(snapshot.spring_host_interference_rows or 0) or int(snapshot.spring_pair_interference_rows or 0):
            st.caption(
                "Пересечения: "
                f"пружина↔цилиндр={int(snapshot.spring_host_interference_rows)}, "
                f"пружина↔пружина={int(snapshot.spring_pair_interference_rows)}"
            )
        return True

    st.markdown(f"**{heading}**")
    cols = st.columns(4)
    with cols[0]:
        st.metric("Строк с геометрией", int(snapshot.rows_with_packaging))
    with cols[1]:
        st.metric("Данных достаточно", int(snapshot.packaging_truth_ready_rows))
    with cols[2]:
        st.metric("Автопроверка OK", int(snapshot.packaging_verification_pass_rows))
    with cols[3]:
        st.metric("Служебный fallback", int(snapshot.runtime_fallback_rows))

    if getattr(snapshot, "status_counts", None):
        st.caption(
            "Статусы по строкам: "
            + ", ".join(f"{name}={count}" for name, count in snapshot.status_counts)
        )

    if int(snapshot.spring_host_interference_rows or 0) or int(snapshot.spring_pair_interference_rows or 0):
        st.warning(
            f"{interference_prefix}: "
            f"пружина↔цилиндр={int(snapshot.spring_host_interference_rows)}, "
            f"пружина↔пружина={int(snapshot.spring_pair_interference_rows)}."
        )
    else:
        st.caption("Пересечений не найдено: 0 по пружина↔цилиндр и пружина↔пружина.")
    return True


__all__ = [
    "has_packaging_snapshot",
    "render_packaging_snapshot_summary",
]
