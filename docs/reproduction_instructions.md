# Reproduction instructions

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install `pytest`.
4. Set `PYTHONPATH` to the package `src/` directory.
5. Run `python -m pytest src/tests`.
6. Compare the supplied CSV/JSON artifacts against `manifests/checksums.txt`.

The release artifacts are deterministic and self-contained. The exact generated instances are in `instances/`; essential result tables and audit summaries are in `outputs/`. The copied Python entry points are exact source copies from the local experiment tree and are provided for transparent reconstruction of the released computational workflow. Their historical repository-relative input/output paths are preserved; do not claim a full standalone regeneration until the authors approve the final release layout. No network access is required.

Expected verification outcome: all included tests pass, the package checksums resolve, and the output schemas match the released CSV/JSON files.

The package does not include internal authority files, protocol records, manuscript drafting history, private paths, credentials, or unpublished audit documents.
