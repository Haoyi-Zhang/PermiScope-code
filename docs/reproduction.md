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

Expected: 87 tests and final status `OK`. Run the same command with `python -O` as a second control; correctness checks do not rely on removable `assert` statements. The exact duration is machine-dependent. Tests also cover dotted declaration collisions, semantic token remapping, changed permissions/classes, invalid certificate reasons/order, source core closure counts, acceptance of all six retained scale certificates, early emission bounds, large integer distances, iterative occurrence traversal, and statement IDs that equal entry display labels. Entry and statement rows partition the fact/rule inventories without double-counting.

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
python compare_framework_results.py results/framework-replay replay-framework
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
- 99 already-exact prefixes (including all new initial facts), 201 requiring rule completion, and 5,220/6,518 semantically reused certificate nodes (80.09%);
- zero campaign errors.

`compare_framework_results.py` excludes the entire summary `resources` block but compares semantic summaries, all CSV rows, and representative evidence files. Inspect the excluded block separately: timing/RSS may vary, but worker count, downloads, platform and resource-limit availability are distinct fields, not timings.

`results/framework-replay` is the retained semantic-catalog baseline. Its timings precede the emission and weighted-boundary changes; they are not measurements of those changes. `results/framework-observed` is the unchanged historical local-token campaign, not a valid byte-equality baseline or current-format certificate package. Comparisons against it are expected to differ. Both campaign drivers use POSIX resource limits when available. On Windows these OS limits are unavailable and the memory field measures peak working set, not Linux RSS. Source/ground bounds and the fixed workload apply on both platforms; run commands under an external timeout when OS limits are unavailable. The ground driver now supports this Windows path as well.

The later Ubuntu 24.04 workflow replay is recorded in `results/measurements/summary.json` and selected raw logs. Its normal and optimized runs both pass 84 tests; its 69 kernel files and 18 framework files match the semantic references. Only timing/RSS vary within the ground results; the source resource block additionally changes platform (`nt` to `posix`) and OS-limit availability (false to true). Worker count remains one and campaign download bytes remain zero. The Linux measurements do not replace the earlier Windows timings in `framework-replay` or the historical ground scale measurements. No whole-workflow elapsed time or independent-replication claim follows from these logs.

## 4. Check one source/evidence pair

```bash
python check_framework.py \
  results/framework-replay/sample-000-source.json \
  results/framework-replay/sample-000-evidence.json
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
  --framework results/framework-replay \
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
