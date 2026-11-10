# Clean-dist verification

- Fresh virtual environment: created successfully.
- `pip install -r requirements.txt`: exit 0.
- Full pytest in the rebuilt dist: `122 passed in 70.88s`.
- `python -m scripts.check_report_consistency`: 20 source tables, 11 required
  sections, 259 prose-number occurrences; 0 unresolved.
- Streamlit health via `curl.exe`: `HTTP/1.1 200 OK`; body `ok`.
- Final package: 167 files, 6,648,988 bytes (6.34 MiB).
- `demo_media/`: 5 PNG images, no demo videos.
- Personal/workspace absolute-path scans: 0 hits. `.github/prompts/`,
  `docs/templates/`, and `_repro_tmp/` are absent from the package.
- The Word report's rendered page count remains unverified; no Word/PDF
  renderer was available.
