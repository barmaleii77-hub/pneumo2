# Profile format (pneumo-profile v1)

A **profile** is a portable JSON containing everything needed to reproduce a run:

- `base`   — base parameters (SI values where applicable)
- `ranges` — optimization ranges (SI values), as `{key: [min, max]}`
- `suite`  — test suite list, same structure as UI table (list of dict rows)
- `meta`   — any metadata (release/build/session id/comment)

## Schema header

```json
{
  "schema": "pneumo-profile",
  "version": 1,
  "meta": { "created_at": "YYYY-MM-DDTHH:MM:SS", "...": "..." },
  "base":   { "...": "..." },
  "ranges": { "param": [0.0, 1.0] },
  "suite":  [ { "имя": "...", "...": "..." } ]
}
```

## Validation

Runtime validation uses `jsonschema` (Draft 2020-12).
The app is intentionally tolerant:
- extra fields are allowed
- `base` values can be any JSON type
- `ranges` must be arrays `[min, max]` of numbers

## Where profiles are stored

UI export button writes to:

- `WORKSPACE_EXPORTS_DIR/profile_YYYYMMDD_HHMMSS.json`

Because `workspace/exports` is included into send-bundle, your profile will be shipped automatically.

## Applying profiles

When you click "Применить профиль":
- base/ranges/suite are loaded into Streamlit state
- the app reruns and shows updated tables
- a small green banner confirms that the profile was applied
