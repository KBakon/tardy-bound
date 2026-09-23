# TARDY-BOUND Reproducibility Package

## Citation

For reproducibility, cite the specific Zenodo version corresponding to the GitHub release used. Zenodo assigns a version-specific DOI to each archived
release.

The repository and its archived releases support only the bounded scientific scope described in the manuscript.

## Purpose

This repository contains computational artifacts supporting the exact verification and reproducibility of the reported bounded theory-state sufficiency/connectivity boundary.

The package is a clean publication artifact, not the complete internal research archive. It contains the release-relevant source code, configurations, generated instance descriptions, and essential verification outputs used to reconstruct the reported result.

## Contents

- `src/`: release copies of the reproducibility code and verification tests;
- `configs/`: frozen run configurations;
- `instances/`: discovery instances and confirmatory Panel A/Panel B instance descriptions;
- `outputs/`: essential discovery, confirmatory, mechanism, and cross-state results;
- `manifests/`: package file inventory and checksums;
- `docs/`: reproduction notes and release metadata.

## Relationship to the manuscript

The manuscript is the scientific publication; this repository is its computational reproducibility companion. The package contains the generated instances, configurations, source entry points, tests, and essential outputs needed to inspect the exact verification route. It is not a replacement for the manuscript and does not contain the internal authority chain or manuscript drafting history.

## Reproduction

Requirements: Python 3.11 or newer, standard-library Python modules, and `pytest` for the verification tests. The scripts use exact integer/rational computations and do not require external data or network access.

From this directory on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pytest
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest .\src\tests
```

The expected test result is a passing verification suite. The supplied CSV/JSON files under `instances/` and `outputs/` are the frozen release artifacts for result reconstruction. The source entry points are retained under `src/`; their outputs are intentionally not regenerated during packaging.

## Expected outputs

Successful verification produces `18 passed` tests in the current release environment. Integrity verification must report zero checksum mismatches against `manifests/checksums.txt`. The released result tables remain the supplied deterministic CSV/JSON artifacts; a full regeneration is a separate author-approved release decision.

The experiment entry points are:

- `src/wp03_microcensus.py` and `src/wp04_signature_audit.py` for discovery/signature checks;
- `src/wp06_mk_v2_rerun.py` for the frozen M_K v2 discovery rerun;
- `src/wp07_witness_audit.py` for the frozen witness mechanism audit;
- `src/wp09_independent_validation.py` for the independent confirmatory panels;
- `src/wp10_cross_state_audit.py` for cross-state exchange telescoping.

The entry points are retained as exact source copies from the local experiment tree. Their historical repository-relative paths are documented in the source and are not silently rewritten in this publication package. The frozen outputs supplied here are the release artifacts for reconstruction; a full regeneration should be performed only after authors decide on the final release layout and rerun policy.

## Scientific scope and limitations

The package supports a bounded, non-empirical computational result. The scope is:

- deterministic;
- static;
- non-preemptive;
- unweighted;
- single-machine total tardiness;
- constructed exact domains.

These artifacts do not establish broader empirical, industrial, real-world, or universal validation. They support exact computation, symbolic verification, and controlled constructed domains only.

## Release status

GitHub repository:
https://github.com/KBakon/tardy-bound

Zenodo archiving is enabled through the GitHub integration. Each published GitHub release is archived as a versioned Zenodo software record with a version-specific DOI.

Release metadata are maintained in `CITATION.cff`. The repository uses MIT licensing for source code and configuration files and CC BY 4.0 for generated research artifacts and documentation.
