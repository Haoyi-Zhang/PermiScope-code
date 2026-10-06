# Coverage-Carrying Permission Extraction

This repository is the standalone artifact for **Coverage-Carrying Permission Extraction for Bounded Evolving Frameworks**. It implements the bounded framework intermediate language **BFIL-1**, an untrusted evidence producer, an independently coded source checker, a direct source interpreter, revision transport, exact finite controls, generated revision cases, line-bounded public AOSP anchors, and prespecified fault fixtures.

## What the artifact establishes

Within the declared BFIL-1 language and bounds, an accepted evidence object has:

1. an exact source inventory and type-correct normalized document;
2. independently reconstructed lower and upper Horn programs and per-source coverage ledgers;
3. exact least-model certificates and query projections;
4. a three-way `must` / `impossible` / `unresolved` classification under independent positive opaque-site completions;
5. a checked minimum number of opaque trigger **occurrences** in a derivation tree;
6. a checked inclusion-minimal set of distinct opaque source sites; and
7. revision reuse only for fully identical catalog-decoded semantic records, mapped to new local indices and followed by complete checking of the revised source and closure.

Method/field declarations use structured owner/member identity, serialized as canonical JSON arrays. Field and direct-target references can use `{"owner": "...", "member": "..."}`; dotted strings are accepted only if unambiguous. Compact `p0/e0/m0/...` tokens are version-local, never cross-version identity. Transport decodes atom and origin tokens, retains allocation classes, and compares full semantic records.

The retained source-level campaign contains exactly 336 cases: 300 deterministic revision pairs, 12 line-bounded public anchors, and 24 fault fixtures. The separate finite ground kernel exhausts 33,296 four-atom programs, 532,736 representative candidate-certificate checks, and 65,016 three-atom revision pairs.

## What it does not establish

This is not a Java, bytecode, native, or production Android frontend. It does not claim sound handling of reflection, dynamic loading, callbacks, lifecycle behavior, exceptions, concurrency, native enforcement, policy intent, vendor forks, or real-device behavior. The 12 AOSP records validate only their retained source lines, one narrow lexical permission primitive, provenance, and a separately supplied BFIL-1 projection. They are not whole-method or whole-framework analyses.

The checker is structurally separate from the producer but was developed in the same research effort. The strict parser/type resolver and the BFIL-1 semantics are the declared trusted computing base. The general arguments are handwritten, not proof-assistant checked or independently audited.

## Repository layout

- `pcpe/source_model.py` — strict BFIL-1 parser, type checks, bounds, inheritance and resolution.
- `pcpe/lowering.py` — untrusted producer-side lowering.
- `pcpe/source_checker.py` — independent source-to-rule reconstruction and evidence checking.
- `pcpe/source_oracle.py` — direct fixed-point interpreter that does not consume Horn rules or certificates.
- `pcpe/evidence.py` — lower/upper evidence construction, classification, and source-site cores.
- `pcpe/weighted.py`, `pcpe/weighted_checker.py` — minimum trigger-occurrence producer and checker.
- `pcpe/source_revision.py` — conservative named-record transport and complete revised closure.
- `pcpe/framework_cases.py` — 300 deterministic old/new source pairs.
- `pcpe/framework_faults.py` — 24 frozen source/evidence mutations.
- `pcpe/java_slice.py`, `pcpe/public_slice.py` — line-bounded public-anchor validation.
- `pcpe/model.py`, `pcpe/checker.py`, `pcpe/oracle.py`, `pcpe/revision.py` — finite ground prerequisite kernel.
- `inputs/` — owned finite inputs, public excerpt records, and trust-boundary declarations.
- `results/observed/` — retained finite-kernel rows and summaries.
- `results/framework-observed/` — historical pre-repair rows/evidence, retained without rewriting; not current-format evidence.
- `results/framework-replay/` — current semantic-catalog campaign rows, representative evidence, and summary.
- `results/measurements/` — later Linux measurements and selected raw test/check logs, without a duplicate scientific result corpus.
- `tests/` — unit and adversarial tests.
- `docs/` — model/proof, frozen protocol, literature calibration, and reproduction notes.
- `claim_evidence_ledger.csv` — claim-to-proof/test/result mapping.
- `reference_audit.csv` — one row for every manuscript reference, including persistent identifier, verification source, relevance role, and access date.
- `public_source_audit.csv` — immutable source provenance for all 12 AOSP anchors, including blob and excerpt digests.
- `external_resources.csv` — external source, license, access, and integration inventory.

## Quick verification

Run from this repository root with Python 3.11 or later. The implementation uses only the Python standard library.

```bash
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python audit_manuscript.py
```

Validate one retained public projection or any BFIL-1 source/evidence pair:

```bash
python check_framework.py \
  results/framework-replay/sample-000-source.json \
  results/framework-replay/sample-000-evidence.json
```

## Full clean reproduction

The following commands write into new directories and do not alter retained observed results:

```bash
python reproduce.py --out replay-kernel
python reconcile.py replay-kernel
python compare_results.py results/observed replay-kernel

python run_framework_campaign.py --out replay-framework
python reconcile_framework.py replay-framework
python compare_framework_results.py results/framework-replay replay-framework
```

The ground comparator excludes four named timing/RSS fields from JSON and no CSV fields. The source comparator excludes its whole summary resource block, so host configuration, worker count and download bytes must be inspected separately. All claim-bearing rows, classifications, counts, proof structures, public records, and fault outcomes must agree. See `docs/reproduction.md` for expected outputs and the paper-data export command.

## Retained headline results

- All 300 generated revision pairs remain distinct after identifier erasure; the new documents also have 300 distinct identifier-erased structures. Each family spans alias depth 0--4, width 0--4, and inheritance/call depth 0--3.
- 300/300 generated lower permission projections agree with the direct empty-completion interpreter, and 300/300 upper permission projections agree with the direct all-enabled interpreter. Full Horn-atom agreement was not measured.
- All 528 directly enumerated completion permission sets lie between the endpoints; for every case their intersection and union equal the lower and upper permission projections.
- 60 queries are unresolved. Minimum opaque-trigger occurrences and inclusion-minimal distinct-site core sizes are distributed identically as 18 cases of size 1, 21 of size 2, and 21 of size 3; the two metrics are checked independently and are not asserted equivalent in general.
- All 24 prespecified faults are rejected at their expected first stage.
- Full lowering is exact on 300/300 new generated documents. Field-insensitive and context-insensitive variants each add 100 permission false positives; class-hierarchy dispatch adds 300. These are designed separators, not production precision estimates.
- The suite contains 150 permission-preserving and 150 permission-changing revisions. The mapped prefix plus all new facts is already exact in 99 cases; the remaining 201 require rule completion before full checking. The current replay reuses 5,220 of 6,518 certificate nodes (80.09%); the historical local-token count was 4,794/6,518 (73.55%). No checker-speedup claim is made.
- The retained Windows semantic-catalog replay records 2,919,349 checker steps, 2,289,440 graph operations, 51.578 process CPU seconds, 54.328 wall seconds, and 46.73 MiB peak working set, with one worker and zero downloads. These measurements precede the emission-limit and weighted-boundary changes and are not timings of those changes. POSIX process limits were unavailable. The older source observation (17.399 CPU seconds, 17.403 wall seconds, 117.17 MiB peak RSS) remains in `framework-observed` and is not a timing of the semantic-catalog implementation.
- The offline manuscript/provenance audit accepts exactly 68 unique, cited references and all 12 source records; every retained excerpt digest is recomputed from the packaged text.

## Later Linux replay

GitHub run `37433546102`, head `b0d4ef6d570845168e53847615b7bd2b7104eb1a`, ran the boundary-repaired artifact in the configured Ubuntu 24.04/Python 3.12 workflow. Its downloaded raw archive was compared locally as data, without executing archive code or rerunning the campaigns. All 69 kernel JSON/CSV files and all 18 framework result files (five CSV files, 12 representative JSON files and the semantic summary) match their retained references. That includes 122,693 kernel CSV rows and 1,836 framework CSV rows. The source resource block was inspected separately: one worker and zero downloads agree with the reference; platform is now POSIX and OS resource limits are available.

| Campaign | Process CPU seconds | Recorded wall seconds | Process peak RSS |
| --- | ---: | ---: | ---: |
| Finite ground kernel | 12.956 | 12.952 (sum of 26 chunk timers) | 53,172 KiB (51.93 MiB) |
| BFIL-1 source | 47.353 | 47.362 (driver body) | 46,140 KiB (45.06 MiB) |

Normal and optimized logs each show all 84 tests passing without skips, failures or errors, in 6.423 and 6.000 seconds respectively. Both reconciliation logs have zero errors; the offline audit accepts 68 reference records and 12 packaged public-source records. This is not full-text verification of every citation or a live upstream-source audit.

`results/measurements/summary.json` retains the exact resource observations and configured caps; adjacent files retain the command list, test logs and selected check logs. The complete scientific outputs remain in their existing reference directories rather than being duplicated here. Paper-data export still uses those reference directories, so its historical measurements are unchanged.

The workflow has a 20-minute job deadline and a 900-second scientific-shell deadline with 15-second kill grace. The shell inherits a 3 GiB address-space cap and an 840-second CPU cap **per process**; the ground driver tightens these to 2 GiB and 600 seconds. The source driver keeps 3 GiB and the inherited 840-second CPU cap. Raw-output upload remains `always()`, including failures. The archive does not contain exact runtime limit values, whole-workflow elapsed time, individual command exit-code records, or the runner image/Python patch version. Run identity comes from the supplied completed-run record, not metadata embedded in the archive. These are single-run Linux observations, separate from the historical Windows working-set measurements above; no cross-host speedup or independent replication is claimed.

## Licenses and external material

The retained ground scale times are end-to-end wall observations including input construction, extraction, validation and JSON output. At 12,800 atoms, the 190.4 ms unseeded row accepts an empty certificate; the 212.0 ms seeded row accepts a complete certificate on a different input. No empty-certificate rejection time is reported. The source site-core checker performs `u+k+2 <= 2u+2` closures, including its final sufficiency/minimality audits.

Project code and owned inputs are MIT licensed. The retained AOSP excerpts remain under Apache License 2.0; the license text and an integration notice are in `third_party/aosp/`. No upstream analyzer implementation is vendored or modified. Scholarly papers and publisher templates are referenced but not redistributed in this standalone repository.
