# How to apply the patch (v6.32 → v6.33 pack)

If you already have **UnifiedPneumoApp_UNIFIED_v6_32_WINSAFE** unpacked, you can apply the patch
instead of copying the whole folder.

## Option A) Using `git apply` (recommended if your folder is a Git repo)

1. Put `diffs/v6_32_to_v6_33.patch` next to your repo.
2. Run:

```bash
git apply diffs/v6_32_to_v6_33.patch
```

## Option B) Using `patch` (Linux/WSL)

```bash
patch -p1 < diffs/v6_32_to_v6_33.patch
```

## Changed files
See `diffs/changed_files.txt`.
