# PACKAGE_INTEGRITY_POLICY

- `PACKAGE_MANIFEST.json` не включает хэш самого себя.
- `PACKAGE_SELFCHECK_REPORT.json` не включает хэш самого себя.
- Selfcheck проверяет наличие mandatory files в корне и в imported subtree.
- Пакет не должен объявлять runtime closure proof.
