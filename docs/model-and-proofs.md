# BFIL-1 model and proof obligations

## 1. Status and scope

This document states the mathematical contract implemented by the artifact. The arguments are handwritten proofs for a finite declarative language and are cross-checked by executable finite tests. They are not proof-assistant developments, Java semantics, or evidence about an arbitrary Android release.

## 2. Source language

A BFIL-1 document is `D = (Π, C, S, E)`.

- `Π` is a finite declared permission inventory.
- `C` is a finite set of classes with single inheritance, typed fields, and methods.
- A method has typed parameters and locals, an optional return type, and a finite ordered body.
- `S` maps a declared service class to a concrete subtype implementation.
- `E` names external entries by service, selector, and argument allocation classes.

The monotone statement forms are:

- `new dst : Class`
- `move dst <- src`
- `store base.field <- src`
- `load dst <- base.field`
- virtual `invoke dst <- recv.selector(args)`
- same-receiver `direct dst <- Owner.method(args)`
- `check Permission`
- `return src` or void return
- `opaque { candidate operations }`

Opaque candidates may be `check`, `move`, `store`, `load`, `invoke`, or `direct`; they may not contain nested opaque statements or returns. Enabling a site executes all of its candidates. Sites are independent positive Boolean choices.

The strict parser rejects unknown keys and operations, duplicate names or statement identifiers, unknown classes/fields/variables/permissions, inheritance cycles, incompatible overrides, invalid service implementations, entry/call arity errors, and incompatible assignment/field/call/return types. Fixed source and ground bounds make all algorithms total.

Method and field identity is the pair `(owner, member)`, serialized as a canonical JSON array (not `owner + "." + member`). Dots remain legal in both components, so `("A.B", "run")` and `("A", "B.run")` are distinct declarations. Field and direct-target references accept objects `{"owner": "...", "member": "..."}`; legacy dotted strings are resolved only when unambiguous. All declarations remain in the inventories and are type checked.

## 3. Ground relations and lowering

For entry `e`, context `c`, method `m`, variable `x`, allocations `o,o'`, field `f`, permission `p`, and opaque site `s`, the normalized atoms are:

- `reach(e,c,m)`
- `pt(e,c,m,x,o)`
- `heap(e,o,f,o')`
- `ret(e,c,m,o)`
- `perm(e,p)`
- `active(e,c,m,s)`

Contexts are roots or one call-site identifiers. Allocations are entry receivers/arguments or syntactic `new` sites. Virtual dispatch uses the receiver allocation class and first overriding method. Field cells retain base allocation and field identity.

Every valid source occurrence deterministically generates a finite family of named facts or positive Horn rules. A record identity contains its logical atom or head/body plus source occurrence, origin, certainty, and weight. The catalog is fixed before emission; no rule creates a new catalog element. Canonical sorting yields a unique normalized IR, coverage ledger, and ground program for a valid document and fixed analysis variant.

Both lowering paths reject at emission before retaining a record that would exceed 20,000 atoms, 40,000 rules, or 120,000 premise incidences. Source limits are 64 classes, 400 methods, 2,000 fields, 4,000 statements, 64 entries, 128 permissions, eight arguments, 32 locals per method, and eight candidates per opaque site. These are inventory bounds, not a uniform elapsed-time or expanded-output bound.

## 4. Direct source semantics and lowering equivalence

A direct state contains finite relations for reachable method contexts, local points-to facts, heap cells, return values, and permission pairs. Entry facts initialize the state. The source transfer operator repeatedly executes all statements in reachable method contexts until no relation grows. It uses the same declared subtyping, dispatch, context, field, and service semantics as the mathematical language, but the executable direct interpreter does not consume producer Horn rules or certificates.

For completion `V` of the opaque sites, the direct interpreter executes candidate operations exactly at sites in `V`. Let `P_V` be the corresponding definite ground program.

**Theorem — direct/lowering equivalence.** For every valid document within source and emitted-ground bounds, fixed full variant, and completion `V`, `pi(L(P_V)) = lfp(F_V)`, where `pi` decodes the non-activation atoms into direct relations.

**Argument.** Put `S* = lfp(F_V)` and `M = L(P_V)`. Extend a direct state `S` by encoding its relations and adding `active(e,c,m,s)` exactly when `s in V` is an opaque site in a reachable `(e,c,m)`; call this `ext(S)`. Every direct effect has a ground representative by the templates, with the same receiver classes, subtyping, dispatch, field identities and one-call-site contexts, so `pi(ext(S)) = S` on representable reachable states.

`ext(S*)` contains entry facts and is closed under definite rules because `S*` is direct-transfer closed. It is closed under triggers by the extension definition. An active candidate guard entails reachability at an enabled site; the remaining premises give exactly the candidate's direct effect in `S*`. Thus `ext(S*)` is a ground model, and ground leastness gives `M subseteq ext(S*)`, hence `pi(M) subseteq S*`.

Conversely, `pi(M)` contains direct entry initialization. Every applicable definite transfer has its ground body in `M` and hence its effect there. At an enabled reachable opaque site, closure derives the active atom and then each applicable candidate effect. Thus `pi(M)` is direct-transfer closed; direct leastness gives `S* subseteq pi(M)`. The two inclusions prove the projection equality. Ground closure also supplies every active atom in `ext(S*)`, giving `M = ext(S*)`. Activation is an auxiliary representation step, so finite iteration prefixes need not be equal.

The campaign compares permission projections at the two endpoints against direct interpretation and enumerates direct completion permission sets. It does not test full Horn-atom equality or construct a Horn program for each intermediate completion.

The theorem is relative to BFIL-1. It does not prove that an external Java/bytecode/native source was completely translated into BFIL-1.

## 5. Ordinary least-model certificates

A ground program is `P = (A,B,R,Q)` with finite atoms, initial facts, definite rules, and query atoms. The immediate-consequence operator is:

`T_P(X) = X ∪ B ∪ { h | (S -> h) in R and S subseteq X }`.

A certificate lists each derived atom at most once in topological order. A node is justified either by initial-fact membership or by one indexed rule whose full body appears earlier. The checker also requires:

- all initial facts are listed;
- every rule is closed over the listed set; and
- the reported query set is exactly the intersection of listed atoms and queries.

**Theorem — ground soundness and existential completeness.** Acceptance implies the listed atoms are exactly `L(P)` and the report is `Q ∩ L(P)`. Every finite valid program admits an accepted founded topological certificate for that exact set and report, with at most `|A|` nodes. An arbitrary certificate with the exact set but a wrong reason or order need not be accepted.

**Argument.** Topological witness induction gives `C subseteq L(P)`. Required facts and full closure make `C` a model; leastness gives `L(P) subseteq C`. Conversely, fixed-point iteration yields a topological selected reason for every first-derived atom.

The exhaustive finite kernel checks 532,736 representative candidate encodings against a classical-model oracle across all 33,296 four-atom programs with at most two distinct rules.

## 6. Source coverage

The producer submits lower and upper normalized IRs, ground programs, exact coverage ledgers, and certificates. The source checker parses the complete source and independently rebuilds all of them. It imports neither producer lowering nor evidence construction, revision transport, the weighted producer, or the direct oracle. It intentionally shares the strict parser/type model; this shared component and the BFIL-1 semantics are the declared trusted computing base.

**Theorem — source coverage and endpoint permission exactness.** If the source checker accepts an endpoint item, its IR/program/coverage triple is exactly the checker reconstruction from the complete BFIL-1 source, every entry and statement occurrence has a coverage row, and the reported permissions are the exact endpoint least-model semantics.

The coverage ledger is redundant for soundness after exact record equality, but localizes mismatches and exposes zero-rule source obligations. Counts alone are never accepted as a substitute for exact records.

## 7. Lower and upper completions

A definite statement appears in both endpoints. The lower program omits opaque candidates. In the upper program, reachable opaque site `s` derives `active(...,s)` through a weight-one trigger rule; every candidate effect is guarded by that active atom and has weight zero. The empty completion equals the lower program and the all-enabled completion equals the upper program.

**Theorem — exact independent-completion envelope.** For every completion `V`:

`L(P-) subseteq L(P_V) subseteq L(P+)`,

and because empty and all-enabled worlds are admissible:

`intersection_V L(P_V) = L(P-)`,

`union_V L(P_V) = L(P+)`.

A query is `must` in the lower model, `impossible` outside the upper model, and `unresolved` otherwise.

This theorem fails for correlated choices when the all-enabled world is inadmissible. The artifact includes an exactly-one counterexample. Correlated, negative, or stateful uncertainty requires a different admissible-world checker.

## 8. Minimum trigger-occurrence proof

The upper program assigns weight one to opaque trigger rules and zero to all other rules. A derivation tree costs the sum of rule weights, counting repeated rule use after tree unfolding. The producer emits one distance per reachable atom and one founded equality witness. The checker validates the witness and every Bellman inequality:

`d(h) <= w(S -> h) + sum_{a in S} d(a)`.

**Theorem — minimum occurrence cost.** Every accepted finite distance is the minimum number of opaque trigger occurrences among finite derivation trees for that atom.

The metric is not the number of distinct sites: a shared trigger can be counted multiple times when a DAG is unfolded into a tree.

Distances are exact nonnegative integers. With `n` founded nodes, body width at most 16 and maximum positive rule weight `W`, a witness has depth at most `n` and cost below `W * 16**n`. The checker bounds integer bit length by the program structure rather than imposing a fixed decimal ceiling. Its linear graph pass counts integer operations; with `L`-bit distances, additions/comparisons cost `O((n+r+b)L)`. Occurrence serialization uses an explicit stack, skips founded zero-cost subtrees, and preserves preorder and duplicate occurrences. Its output can still be exponential in DAG size.

## 9. Inclusion-minimal distinct-site core

For an unresolved query, deterministic deletion starts with all sites and removes a site whenever the query remains reachable. The checker independently recomputes closure on the returned set and on every one-site deletion.

**Proposition — core guarantee.** The returned set enables the query and no proper subset does.

Monotonicity proves that if deleting a retained site made the query unreachable at the time of the test, the final smaller set without that site is also unreachable. The result is inclusion-minimal, not minimum-cardinality or unique.

The implemented source checker uses exactly `u+k+2 <= 2u+2` closures per unresolved query: initial sufficiency, `u` greedy deletion trials, final sufficiency and `k` deletion audits for the returned `k`-site core. This differs from the simpler optional-fact kernel's `u+1` construction.

## 10. Revision transport

Transport decodes each version's local atom and origin tokens under that version's catalog. Reuse requires equality of entire structured semantic fact/rule records, including decoded head/body, source, origin, certainty, weight, allocation classes and analysis variant. A stable tuple is then mapped to the new local atom/rule indices. Equal `p0` or `e0` tokens alone never establish reuse. Old selected nodes replay in topological order only when their mapped premises are already established. All new facts are inserted, then deterministic scans complete the new least model. The ordinary checker validates the result, and the source checker independently reconstructs the entire new source. The tested pre-completion prefix includes all new initial facts, not old nodes alone.

**Theorem — transport safety.** Every accepted revised result is the exact least-model permission semantics of the revised BFIL-1 source, regardless of reuse count.

A structurally conservative prefix may reject an equal model if a selected witness disappears while an alternative survives. Conversely, witness-only replay without full closure can accept a changed model. The exhaustive three-atom revision study contains 678 examples of the first phenomenon and 9,930 of the second; conservative transport never accepts a changed model.

## 11. Proof maturity

| Claim | General argument | Executable control | Maturity |
|---|---|---|---|
| Finite unique lowering | Finite catalog enumeration | Parser/lowering tests and canonical equality | Handwritten proof + tested implementation |
| Direct/lowering equivalence | Projection/extension and leastness in both directions | Independent direct permission projections on generated endpoints and completions; no full-atom empirical comparison | Handwritten proof + permission projection finite checked |
| Ground exactness | Witness induction and model sandwich | Exhaustive four-atom oracle | Handwritten proof + exhaustive bounded check |
| Source coverage | Complete enumeration and exact equality | Omission/substitution fixtures | Handwritten proof + adversarial tests |
| Completion endpoints | Positive monotonicity and endpoint worlds | All 528 retained completions | Handwritten proof + exact campaign control |
| Minimum occurrence | Bellman lower bound + founded equality | Weighted corruption fixture and unit tests | Handwritten proof + checked certificates |
| Inclusion-minimal core | Greedy deletion monotonicity | All proper one-site deletions; completion oracle | Handwritten proof + checked cases |
| Transport safety | Surviving founded nodes + new closure | Exhaustive ground revisions and 300 source revisions | Handwritten proof + finite/exhaustive checks |

No row denotes mechanized proof or independent external review.
