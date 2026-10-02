# Reproduction guide

## Requirements

- Python 3.11 or later
- standard library only
- one CPU worker is sufficient
- writable space for two replay directories (well below the project limits)

No network, GPU, external model service, package installation, private dataset, Android build, or device is required.

## 1. Unit and adversarial tests

From the standalone repository root:

```bash
python -m unittest discover -s tests -v
```

Expected: 61 tests and final status `OK`. Run the same command with `python -O` as a second control; correctness checks do not rely on removable `assert` statements. The exact duration is machine-dependent. Tests cover strict parsing and bounds, all statement templates, source-checker separation, lower/upper classifications, all-completion endpoint checks, minimum trigger costs, site-core replay, revision transport, public records, and the finite kernel.

## 2. Reproduce the finite ground campaign

```bash
python reproduce.py --out replay-kernel
python reconcile.py replay-kernel
python compare_results.py results/observed replay-kernel
```

Expected comparator result: semantic match. `reconcile.py` recounts every raw table and validates cross-file totals. `compare_results.py` ignores run-specific timing/resource fields but compares all claim-bearing content.

## 3. Reproduce the BFIL-1 campaign

```bash
python run_framework_campaign.py --out replay-framework
python reconcile_framework.py replay-framework
python compare_framework_results.py results/framework-observed replay-framework
```

Expected summary:

- 300 generated revision pairs;
- 150 preserving and 150 changing;
- 60 unresolved queries, with minimum-occurrence/core-size histograms 1:18, 2:21, 3:21;
- 528 enumerated completion models;
- 300 exact endpoint envelopes;
- 24/24 expected fault rejections;
- 12/12 public record acceptances;
- full baseline exact on 300/300 cases;
- field-insensitive and context-insensitive precision 0.75 on the designed aggregate;
- class-hierarchy precision 0.50 on the designed aggregate;
- 300 identifier-erased unique revision-pair structures and 300 unique new-program structures;
- 99 already-exact transported prefixes, 201 requiring completion, and 4,794/6,518 reused final nodes;
- zero campaign errors.

`compare_framework_results.py` excludes timing and process RSS but compares semantic summaries, all CSV rows, and representative evidence files.

## 4. Check one source/evidence pair

```bash
python check_framework.py \
  results/framework-observed/sample-000-source.json \
  results/framework-observed/sample-000-evidence.json
```

Expected: accepted source evidence. This case contains the field-sensitive running example and two nested opaque sites.


## 5. Audit bibliography and public-source provenance

```bash
python audit_manuscript.py
```

When the artifact is inside the full project, also run:

```bash
python audit_manuscript.py --paper-dir ../paper
```

The standalone check validates the 68-row reference inventory and the 12 source records. The project-aware form additionally requires exactly 68 unique bibliography entries, no undefined or uncited entry, exact title/key agreement with `reference_audit.csv`, and recomputed excerpt digests. The audit is offline; it checks the packaged verification record, not live publisher availability.

## 6. Regenerate paper data

When the artifact is beside the project paper directory:

```bash
python export_paper_data.py \
  results/observed \
  --framework results/framework-observed \
  --out ../paper/data
```

This writes LaTeX macros and tables from retained summaries. It does not edit prose or figures. After export, rebuild the paper from `paper/` using `sh build.sh` and visually inspect every page.

## 7. Interpretation of success

A successful command shows that the provided implementation reproduces its retained bounded evidence. It is not an independent proof of parser correctness, the handwritten theorems, full Java/Android coverage, or production performance. The direct interpreter and exhaustive classical-model oracle reduce shared-implementation risk but do not eliminate it.

## 8. Troubleshooting

- Run commands from the repository root so relative input paths resolve.
- Do not place replay output inside `results/observed` or `results/framework-observed`.
- If a semantic comparison fails, inspect the first reported file/field rather than replacing retained output.
- Timing/RSS differences are expected. Semantic rows, proof structures, classifications, and counts are not.
