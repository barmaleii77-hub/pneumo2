# TODO / Wishlist addendum — R31AA (2026-03-25)

## TODO delta
- Root cause for Web UI idle CPU narrowed to browser-side hidden-tab / duplicate-loop behaviour, not only Qt/OpenGL.
- Hidden / zero-size / CSS-hidden Streamlit iframes must be treated as off-screen everywhere browser followers run.
- Measured Windows SEND-bundle acceptance is still open for Web UI CPU after detail-run / stop playback.

## Wishlist delta
- Browser performance acceptance should export wakeup counters / duplicate-loop guard hits per component.
- Hidden-tab gating must be treated as a first-class regression gate for Streamlit iframe-based views.
- Future SEND bundles should include browser-side idle-loop telemetry so CPU regressions stop being “felt only by the user”.
