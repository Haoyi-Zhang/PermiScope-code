# Literature calibration and novelty boundary

## Purpose and method

This note records the literature used to choose the research question, set the evidence standard, and calibrate the manuscript's structure. It is not a systematic literature review and does not use citation counts as evidence of novelty. The selection has three strata:

1. twelve IEEE Transactions on Software Engineering articles used to calibrate journal-style problem framing, method exposition, evaluation breadth, and limitations;
2. five foundational works used to delimit the formal claims; and
3. five closest adjacent works used to test whether the proposed contribution is already known.

Access depth is explicit. `F` means a full publisher text, author manuscript, or open preprint was inspected; `O` means the publisher abstract, section outline, metadata, and any accessible introduction text were inspected; `A` means abstract and bibliographic metadata only. No paper, codebase, or dataset is redistributed in this artifact. Access date is 2026-09-17 unless noted. Access labels describe the material actually inspected; they do not imply reproduction of the cited artifact.

## Same-venue calibration: twelve TSE articles

| Study | Access | Problem and organizing principle | Evidence pattern | Calibration consequence for this work |
|---|---:|---|---|---|
| Bartel et al., *Static Analysis for Extracting Permission Checks of a Large Scale Framework* (TSE 40(6), 2014, DOI 10.1109/TSE.2014.2322867) | F | Starts from failure of off-the-shelf analysis, then introduces Android-specific class-hierarchy, field-sensitive, and initialization treatments. | Framework-scale empirical study, explicit assumptions and limitations, code/mapping tables. | The motivating domain is legitimate, but any claim about Android must be tied to a real frontend and source coverage. BFIL-1 is therefore stated as a bounded language, not a replacement for the 2014 extractor. |
| Wang et al., *Runtime Permission Issues in Android Apps* (TSE 49(1), 2023, DOI 10.1109/TSE.2022.3148258) | F | Builds a taxonomy from issue reports, then triangulates with a survey, interviews, temporal trends, and tool evaluation. | 135 Stack Overflow posts, 199 project issues, practitioner evidence, tool assessment. | A TSE manuscript should connect formal machinery to stakeholder-visible failure modes. Our paper therefore separates source omissions, inference faults, uncertainty, and stale revision evidence rather than reporting one aggregate accuracy number. |
| Li et al., *Android Custom Permissions Demystified* (TSE 48(11), 2022, DOI 10.1109/TSE.2021.3119980) | O | Uses targeted fuzzing and source investigation to move from individual failures to design shortcomings and mitigations. | Thousands of generated cases, manually investigated critical paths, confirmed CVEs. | Generated cases must be prespecified, interpretable, and connected to concrete fault classes. Our 24 mutations are therefore named by first failed contract stage and are not presented as organic Android bugs. |
| He et al., *Efficient Summary Reuse for Software Regression Verification* (TSE 48(4), 2022, DOI 10.1109/TSE.2020.3021477) | O | Reuses procedure and loop summaries within CEGAR and adds lazy counterexample analysis. | 3,675 revisions of 488 Linux drivers; reports 84--93% time savings. | Revision reuse itself is not novel. Our contribution is deliberately narrower: reuse is only a candidate prefix, while complete new-source reconstruction and closure remain mandatory; no checker-speedup claim is made. |
| Fluri et al., *Change Distilling* (TSE 33(11), 2007, DOI 10.1109/TSE.2007.70731) | F | Defines a fine-grained change taxonomy and an AST-matching/edit-script algorithm. | 1,064 manually classified changes in 219 revisions; compares to a prior differencer. | Evolution claims need a declared edit universe and an independent oracle. The BFIL revision suite fixes the edit generator before the full run and records preserving and changing cases separately. |
| Mens and Tourwé, *A Survey of Software Refactoring* (TSE 30(2), 2004, DOI 10.1109/TSE.2004.1265817) | F | Organizes a broad field by activities, formalisms, artifacts, tool issues, and process effects, supported by a running example. | Structured comparison rather than a new benchmark. | Terminology must distinguish behavior preservation, syntactic identity, and analysis-result equality. The manuscript never equates conservative transport rejection with semantic change. |
| Afrose et al., *Evaluation of Static Vulnerability Detection Tools With Java Cryptographic API Benchmarks* (TSE 49(2), 2023, DOI 10.1109/TSE.2022.3154717) | F | Constructs controlled and real-code benchmarks with both misuse and correct cases, then compares multiple tools. | 181 unit cases plus 121 cases from ten Apache projects; precision/scalability analysis. | Controlled separators and real anchors serve different roles. Our 300 BFIL cases measure exact semantics of the bounded language; the 12 AOSP excerpts are provenance/lexical anchors only. |
| Cai et al., *Design Rule Spaces* (TSE 45(7), 2019, DOI 10.1109/TSE.2018.2797899) | O | Introduces an architectural representation, an ArchRoot algorithm, and project-level quality analysis. | Fifteen open-source projects, longitudinal architectural observations. | A representation paper must show what the representation exposes. The coverage ledger is therefore justified as a local diagnostic object even though exact IR equality is already sufficient for acceptance. |
| Kamei et al., *A Large-Scale Empirical Study of Just-in-Time Quality Assurance* (TSE 39(6), 2013, DOI 10.1109/TSE.2012.70) | O | Reframes defect prediction around risky changes and effort-aware review. | Six open-source and five commercial projects; accuracy, recall, and effort-aware results. | Evaluation claims must be matched to sampling units. We report exact counts over designed BFIL revisions and do not generalize their precision values to production frameworks. |
| Ponta et al., *A Manually Curated Dataset of Fixes to Vulnerabilities of Open-Source Software* (TSE 48(5), 2022) | F | Treats curation provenance and reproducibility as first-class contributions. | Vulnerability-to-fix mappings, scripts, and open data lineage. | Every public excerpt in this artifact carries repository, immutable tag, path, lines, excerpt text, license, and a separate bounded projection. |
| Guyon et al., *Evaluating the Impact of Design Pattern and Anti-Pattern Dependencies on Change-Proneness* (TSE 34(5), 2008) | O | Connects structural dependencies to change-proneness through explicit hypotheses and empirical models. | Multi-system empirical analysis and statistical interpretation. | Structural labels must not silently become causal claims. Our field/context/CHA variants are designed semantic ablations, not estimates of real-world defect causes. |
| Selby et al., *Cleanroom Software Development: An Empirical Evaluation* (TSE SE-13(9), 1987, DOI 10.1109/TSE.1987.233525) | F | Evaluates a disciplined development method with controlled teams and separates process, product, and human outcomes. | Fifteen three-person teams, ten treatment and five comparison teams. | The paper separates method guarantees from observed process costs and explicitly reports the checker trusted base and lack of independent authorship/replication. |

An additional historical calibration is Weiser's *Program Slicing* (TSE SE-10(4), 1984), which reinforces the value of a precise semantic object and carefully bounded examples. It is not included in the current manuscript bibliography and is not needed to reach the twelve-paper count.

### Same-venue narrative pattern extracted

The recurring TSE structure is: a concrete and consequential problem; an explicit model or taxonomy; a method whose assumptions are visible; evidence at multiple scales; direct comparison or falsifying controls; threats and boundary conditions; and a practical interpretation that does not outrun the data. Tables carry corpus definitions, comparisons, and failure categories. Figures explain architecture or a motivating counterexample rather than decorate the paper. This pattern motivated the main paper's omission counterexample, formal contract, independently checked endpoint semantics, prespecified campaign, ablations, fault stages, public provenance table, and production-frontend obligations.

## Five foundational works

| Work | Role in the boundary | Consequence |
|---|---|---|
| Cousot and Cousot, *Abstract Interpretation* (POPL 1977) | Least fixed points and sound abstraction are established foundations. | The paper does not claim novelty for monotone fixed-point reasoning. |
| Necula, *Proof-Carrying Code* (POPL 1997) | A small consumer checking producer-supplied evidence is established. | The novelty claim cannot be “evidence plus a checker”; it must concern the source-coverage object and bounded uncertainty semantics. |
| Pnueli et al., *Translation Validation* (TACAS 1998) | Per-run validation can replace trust in a complex transformer. | Source-to-rule reconstruction is framed as validation of each BFIL lowering, not verification of a general compiler. |
| Au et al., *PScout* (CCS 2012) | Android permission specifications can be inferred from framework code. | Practical Android mapping is prior art; the current artifact does not claim a new Android mapping. |
| Arzt et al., *FlowDroid* (PLDI 2014) | Context-, flow-, field-, object-, and lifecycle-sensitive Android analysis establishes a much richer production-analysis bar. | BFIL's one-call-site context and monotone semantics are stated as restrictions, not competitive production precision. |

## Five closest adjacent works

| Work | Existing result | Remaining delta tested here |
|---|---|---|
| Tantow et al., *Verifying Datalog Reasoning with Lean* (ITP 2025, DOI 10.4230/LIPIcs.ITP.2025.36) | Formally verified Datalog proof-tree/DAG checking and model checking for completeness. | BFIL source obligations are reconstructed before the ground checker; the current handwritten checker is not stronger than the Lean result. |
| Albert, Arenas, and Puebla, *An Incremental Approach to Abstraction-Carrying Code* (LPAR 2006, DOI 10.1007/11916277_26) | Incremental certificates and dependency-aware checking for changed programs. | Transport is not claimed as a new general incremental scheme. The delta is mandatory full revised-source coverage and endpoint closure in the BFIL contract. |
| Gorski et al., *ACMiner* (CODASPY 2019) | Mines Android middleware authorization checks with domain-specific analysis. | A complete Android authorization model remains outside BFIL; opaque sites expose unsupported source rather than silently approximating it. |
| Li et al., *Cross-Language Android Permission Specification* / NatiDroid (ESEC/FSE 2022, DOI 10.1145/3540250.3549142) | Crosses Java/native boundaries and evaluates on more than 11,000 apps. | The current work has no native frontend or app-scale evaluation; this is an explicit nonclaim. |
| Bagheri et al., *Detection of Design Flaws in the Android Permission Protocol Through Bounded Verification* (FM 2015, LNCS 9109) | Uses bounded verification to find permission-protocol design flaws. | BFIL is a bounded extraction/evidence language, not a model of the complete Android permission protocol. |

Recent call-graph-soundness and conditional-implicit-call studies were also checked because they make the source-omission threat concrete. They strengthen the motivation for an explicit unsupported-source state, but they also show why BFIL results cannot be generalized to Java/Android without a substantially richer frontend.

## Competing formulations rejected or demoted

1. **A proof DAG for every reported permission.** Rejected as the primary contribution because it detects unfounded positive claims but not omitted source semantics; formally verified Datalog checkers are already stronger.
2. **Proof DAG plus a closure scan over producer rules.** Demoted to the ground assurance kernel. It proves the least model only if the supplied rule inventory is complete.
3. **Witness-only replay after a revision.** Refuted: all old witnesses can remain valid while a new source construct enables an omitted permission. The finite revision suite retains 9,930 such false accepts.
4. **Generic incremental certificate transport.** Rejected as a novelty claim because incremental abstraction-carrying code and regression verification already address broader reuse schemes.
5. **A unique least unresolved source set.** Refuted by incomparable alternatives. The implemented guarantee is deterministic inclusion-minimality, not uniqueness or minimum cardinality.
6. **Minimum number of distinct opaque sites from a simple weighted DAG.** Rejected because tree unfolding counts repeated trigger occurrences. Distinct-site diagnosis is checked separately by deletion.
7. **All minimal unresolved cores can be enumerated efficiently because rules are acyclic.** Rejected: an acyclic width-two family has exponentially many minimal sets.
8. **Treat every unknown source fragment as enabled.** Rejected as a complete answer because it loses the must/impossible/unresolved distinction. Upper and lower endpoints are both retained.
9. **Use public AOSP snippets as evidence of a Java frontend.** Rejected. The excerpts validate immutable provenance, exact line text, and one lexical permission primitive only; their BFIL projections are separate owned models.
10. **Claim production precision from designed ablations.** Rejected. The 0.75 and 0.50 precision values are exact for the constructed separator suite only.
11. **Claim checker independence from code separation.** Rejected. The producer and checker are separately implemented but share the parser/type model and were developed in one effort; that shared base is disclosed.
12. **Call the 300 generated revisions a representative framework sample.** Rejected. They are deterministic proof-obligation cases, useful for falsification and exact replay but not statistical sampling of Android evolution.

## Novelty statement that survived calibration

The defensible contribution is a bounded composition, not any one standard component: for the fully declared BFIL-1 source language, the consumer independently reconstructs a complete named lowering and coverage ledger, checks exact lower and upper least models for explicit positive opaque sites, validates minimum trigger-occurrence and inclusion-minimal source-site explanations, and permits structural reuse only before complete revised-source and closure checking. The theorem is relative to BFIL-1 and its parser/type semantics. It neither verifies a Java frontend nor improves on formal Datalog checker assurance.

## Bibliographic quality-control decisions

The final bibliography was reconciled against canonical DOI, publisher, proceedings, or DBLP records. Material corrections include APER's page range (125--137), the FM 2015 identity of Bagheri et al.'s bounded-verification paper, DroidRA's ISSTA venue, SEALANT's title and author list, the original CASCON record for Soot, and the titles/authors of the 2008 and 2012 abstraction-carrying-code articles. The 2021 incremental-Datalog, LPAR 2006 incremental ACC, 2022 TSE summary-reuse, and 2026 conditional-call records were also checked.

The manuscript contains exactly 68 references. `reference_audit.csv` records a persistent identifier or canonical proceedings record, verification source, relevance role, status, and access date for every entry. `audit_manuscript.py --paper-dir <paper>` rejects duplicate keys/titles, missing or uncited entries, audit/bibliography title disagreement, and malformed verification records. This is a bibliographic identity and relevance audit; it is not evidence that every cited implementation was executed or every paper was reproduced. Closest-work access notes and official workflow sources remain in `external_resources.csv`.
