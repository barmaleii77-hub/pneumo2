# GitHub push instructions for repo `barmaleii77-hub/pneumo2`

Prepared from release archive: `PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03.zip`
Selected product release: `PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03`
Selected release tag: `R176_R31CN_HF8`

## Option A — start from the git bundle
```bash
mkdir pneumo2-import
cd pneumo2-import
git clone -b main /path/to/pneumo2_R31CN_HF8.git.bundle pneumo2
cd pneumo2
git remote add origin https://github.com/barmaleii77-hub/pneumo2.git
git push -u origin main
```

## Option B — upload the working tree into an existing clone
Unpack `pneumo2_R31CN_HF8_repo_root.zip` into the repository root, then:

```bash
git add .
git commit -m "Import PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03"
git push origin main
```

## Notes
- The working tree archive contains the exact extracted source tree with the top-level release folder stripped.
- The git bundle contains one local commit on `main` built from that exact tree.
- If the remote repository already has commits, review history before pushing.
