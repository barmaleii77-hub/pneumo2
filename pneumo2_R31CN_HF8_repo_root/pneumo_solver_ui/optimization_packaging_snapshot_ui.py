from __future__ import annotations

from typing import Any


def has_packaging_snapshot(snapshot: Any) -> bool:
    return snapshot is not None and int(getattr(snapshot, "rows_with_packaging", 0) or 0) > 0


def render_packaging_snapshot_summary(
    st: Any,
    snapshot: Any,
    *,
    compact: bool = False,
    heading: str = "Packaging snapshot",
    interference_prefix: str = "В run есть packaging-interference evidence",
) -> bool:
    if not has_packaging_snapshot(snapshot):
        return False

    if compact:
        st.caption(
            "Packaging snapshot: "
            f"rows={int(snapshot.rows_with_packaging)}, "
            f"truth_ready={int(snapshot.packaging_truth_ready_rows)}, "
            f"autoverif_pass={int(snapshot.packaging_verification_pass_rows)}, "
            f"fallback={int(snapshot.runtime_fallback_rows)}"
        )
        if int(snapshot.spring_host_interference_rows or 0) or int(snapshot.spring_pair_interference_rows or 0):
            st.caption(
                "Interference: "
                f"spring↔cylinder={int(snapshot.spring_host_interference_rows)}, "
                f"spring↔spring={int(snapshot.spring_pair_interference_rows)}"
            )
        return True

    st.markdown(f"**{heading}**")
    cols = st.columns(4)
    with cols[0]:
        st.metric("Rows", int(snapshot.rows_with_packaging))
    with cols[1]:
        st.metric("Truth-ready", int(snapshot.packaging_truth_ready_rows))
    with cols[2]:
        st.metric("Autoverif PASS", int(snapshot.packaging_verification_pass_rows))
    with cols[3]:
        st.metric("Runtime fallback", int(snapshot.runtime_fallback_rows))

    if getattr(snapshot, "status_counts", None):
        st.caption(
            "Packaging status rows: "
            + ", ".join(f"{name}={count}" for name, count in snapshot.status_counts)
        )

    if int(snapshot.spring_host_interference_rows or 0) or int(snapshot.spring_pair_interference_rows or 0):
        st.warning(
            f"{interference_prefix}: "
            f"spring↔cylinder={int(snapshot.spring_host_interference_rows)}, "
            f"spring↔spring={int(snapshot.spring_pair_interference_rows)}."
        )
    else:
        st.caption("Interference rows: 0 по spring↔cylinder и spring↔spring в packaging summary.")
    return True


__all__ = [
    "has_packaging_snapshot",
    "render_packaging_snapshot_summary",
]
