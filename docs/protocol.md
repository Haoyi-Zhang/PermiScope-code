# Frozen evaluation protocol

## 1. Research questions

- **RQ1 — agreement and rejection.** Does the independent checker agree with direct semantics and reject source, coverage, certificate, weighted, and classification faults?
- **RQ2 — unresolved evidence.** Do endpoint, minimum trigger-occurrence, and inclusion-minimal source-site claims hold over every declared completion in the retained cases?
- **RQ3 — controlled abstraction variants.** Do field-insensitive, context-insensitive, and class-hierarchy variants separate on cases constructed to require the omitted dimension?
- **RQ4 — revision transport.** Does structural transport distinguish preserved from changed results while retaining surviving named evidence?

No hypothesis depends on a preselected speedup. A mismatch, accepted fault, endpoint-envelope failure, changed-model transport acceptance, or paper/result inconsistency falsifies the corresponding claim.

## 2. Source-level campaign: exactly 336 cases

### 2.1 Generated revisions: 300

`pcpe/framework_cases.py` deterministically constructs 100 old/new pairs in each family:

1. **Field family.** Two guard objects are stored in distinct fields. The revision preserves or changes which field is loaded before virtual dispatch.
2. **Context family.** Two calls through an identity helper carry different guard objects. The revision preserves or changes which call-site result reaches the guard invocation.
3. **Hierarchy/service family.** A declared service has multiple implementations. The revision preserves or changes the concrete implementation selected by the service entry.

Each family has 50 permission-preserving and 50 permission-changing pairs. The 100 profiles per family form a deterministic grid over alias depth 0--4, width 0--4, and inheritance/call depth 0--3. Twenty profiles per family contain one to three opaque sites arranged so that every site is required for the additional permission. Preserving revisions deliberately mix three situations: unchanged proof-relevant structure, reachable semantics-preserving refactoring, and closure-neutral additions. Family labels and expected revision class are fixed by construction, not inferred after running.

The campaign computes canonical signatures after erasing identifiers and rejects the suite unless all 300 revision pairs and all 300 new programs remain structurally distinct. Separate maxima across the retained suite are 32 methods, seven fields, 63 statements, 1,415 upper atoms, 3,486 upper rules, 9,254 premise incidences, and 49 selected certificate nodes. These maxima occur in different items and do not describe one joint workload.

### 2.2 Public line-bounded anchors: 12

Six records come from `VibratorManagerService.java` and six from `WallpaperManagerService.java` at AOSP tag `android-14.0.0_r1`. Each JSON record retains:

- repository and immutable tag;
- source path and exact line range;
- exact excerpt, Git blob SHA-1, and excerpt SHA-256;
- Apache-2.0 attribution;
- one recognized `enforceCallingOrSelfPermission` permission expression; and
- a separate BFIL-1 projection.

The validator checks the retained line range, narrow lexical primitive, metadata, and projection. It does not parse surrounding Java, resolve aliases, interpret control flow, or claim whole-method/framework completeness.

### 2.3 Fault fixtures: 24

The fixtures are generated before execution and contain one named mutation each.

- 12 source-validation faults: duplicate statement/class, unknown supertype, inheritance cycle, unknown field type, incompatible override, invalid service subtype, entry arity, unknown permission/variable/field, unsupported opaque candidate.
- 3 evidence schema faults.
- 5 IR/program/coverage mismatches across lower and upper endpoints.
- 2 ground-certificate faults.
- 1 weighted-distance fault.
- 1 classification fault.

Each fixture specifies its expected first rejection reason. Passing a later check does not compensate for a wrong first-stage outcome.

## 3. Completion protocol

For every new generated source, the direct interpreter enumerates every subset of opaque sites. Retained cases have at most three sites, yielding 528 completion runs across 300 sources. For each source the campaign checks:

- lower Horn permissions equal the direct empty completion;
- upper Horn permissions equal the direct all-enabled completion;
- every completion lies between lower and upper;
- the intersection of completion results equals lower;
- the union equals upper;
- each reported classification matches membership in all/no/some completions;
- each returned site core enables the query and every one-site deletion disables it.

This is exact for the retained independent-site models, not a sample of a larger uncertainty space.

## 4. Baselines and variants

All variants receive the same valid source, entries, permissions, and resource access.

- **Full BFIL-1:** one-call-site context, field-sensitive heap, receiver-points-to dispatch.
- **Field-insensitive:** merges field identities while retaining the other dimensions.
- **Context-insensitive:** merges call-site contexts while retaining fields and points-to dispatch.
- **Class hierarchy:** considers every subtype implementation compatible with the static receiver/service type.
- **Witness-only revision checker:** replays old witnesses but intentionally omits full new closure; it is a negative control, not a proposed safe method.
- **Whole recomputation:** ordinary fresh certificate construction is the semantic reference for transport.

Variant precision over generated cases is a designed separation result. It must not be reported as an estimate of Android analyzer precision or prevalence.

## 5. Finite ground prerequisite campaign

### 5.1 Exact least-model checker

Four atoms yield 64 possible ground clauses when any body subset may imply any head. The campaign enumerates all theories with zero, one, or two distinct clauses and all 16 initial-fact masks: 33,296 programs. For each, 16 representative candidate truth-set encodings are checked against a separate classical-model enumeration: 532,736 checks.

### 5.2 Revision space

Three atoms yield 24 possible clauses and 301 theories with at most two rules. Each theory/fact mask is paired with every one-fact toggle and every one-rule toggle, producing 65,016 revision pairs. The protocol compares oracle models, fresh certificates, conservative transport, and witness-only replay.

### 5.3 Optional facts and cores

For every three-atom theory, each atom is known, optional, or absent: 8,127 partial programs. The campaign evaluates 24,381 query classifications and 48,762 core requests in forward and reverse deletion orders. All positive completions and all proper subsets of each returned core are checked.

### 5.4 Boundary and scale controls

Independent-pair families of size one through six establish an elementary exponential output count for enumerating all minimal cores. An exactly-one completion demonstrates that the lower/upper union theorem requires admissible all-enabled choices.

Scale inputs have 128, 1,280, and 12,800 atoms with 400, 4,000, and 40,000 premise incidences, with zero or one seed respectively. The empty and complete certificates are both accepted on their distinct inputs. The retained 190.4/212.0 ms observations are end-to-end wall times including construction, extraction, validation and JSON output, not isolated checker latency or an empty-certificate rejection time. These are ground probes, not framework methods or call-graph edges.

## 6. Measurements and retained outputs

Claim-bearing results are semantic rows and counts. Timing and memory are descriptive single-run observations.

- `results/framework-observed/generated-revisions.csv`
- `results/framework-observed/baseline-results.csv`
- `results/framework-observed/fault-fixtures.csv`
- `results/framework-observed/public-slices.csv`
- `results/framework-observed/summary.json`
- representative source/evidence pairs for two cases per family
- `results/observed/*.csv` and `*-summary.json` for the finite kernel

Those `framework-observed` paths preserve the historical source campaign. The current `results/framework-replay/` reruns the same workload with structured declaration identities and catalog-decoded reuse. It records 5,220/6,518 semantically reused nodes (80.09%), 2,919,349 checker steps, 2,289,440 graph operations, 51.578 process CPU seconds, 54.328 wall seconds and 46.73 MiB peak Windows working set, one worker and zero downloads. The earlier source timings (17.399 CPU seconds, 17.403 wall seconds, 117.17 MiB RSS) are not observations of revised code. The historical finite kernel records 16.318 CPU seconds and 117.17 MiB peak RSS. These are descriptive observations, not comparative performance claims.

## 7. Inclusion, exclusion, and non-claims

Included: deterministic owned BFIL-1 inputs, exact finite enumeration, immutable line-bounded AOSP excerpts, independent executable paths, prespecified structural faults, and clean replay.

Excluded: private data, human participants, model APIs, GPUs, real devices, full Android builds, native execution, upstream-tool modification, stochastic tuning, and statistical population inference.
