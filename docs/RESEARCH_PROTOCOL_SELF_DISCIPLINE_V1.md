# HDS Research Protocol v1 — Self-Discipline

**Protocol status:** planned, not yet executed  
**Version:** 1.0  
**Research question:** What is self-discipline, what components does it include, and which interventions have evidence for developing it?  
**Integrity rule:** This protocol describes how evidence will be found and evaluated. It is not itself a finding and must not be cited as evidence that an intervention works.

## 1. Objectives

1. Map how peer-reviewed research defines and measures self-discipline.
2. Distinguish self-discipline from related but non-identical constructs, including self-control, conscientiousness, grit, habit, executive function, motivation, and emotion regulation.
3. Identify correlates, predictors, mechanisms, and interventions without treating these categories as interchangeable.
4. Assess the strength, consistency, directness, and limitations of evidence for interventions.
5. Produce a traceable report separating established findings, qualified interpretations, hypotheses, and opinions.

## 2. Search plan

### Sources

- PubMed / MEDLINE
- Crossref bibliographic records
- Follow-up reference-list checking for eligible systematic reviews and meta-analyses, once their full texts or reference lists are available

Crossref is a metadata discovery service, not a quality rating system. PubMed indexing does not, by itself, mean that a paper is high quality.

### Search concepts

Run separate searches rather than relying on one broad query. Save the exact query, provider, date/time, result count, and retrieval run ID for every search.

**A. Definitions and measurement**
- ("self-discipline" OR "self discipline") AND (definition OR construct OR measure OR scale OR measurement)
- (self-control OR self-regulation) AND (conceptualization OR measurement OR scale)

**B. Reviews of interventions**
- ("self-discipline" OR self-control OR self-regulation) AND (systematic review OR meta-analysis) AND (intervention OR training OR improve OR development)
- (self-control training OR self-regulation intervention) AND (systematic review OR meta-analysis)

**C. Primary intervention studies**
- ("self-control" OR "self-regulation" OR "self-discipline") AND (randomized OR trial OR intervention OR training)
- ("implementation intentions" OR habit formation OR goal setting) AND (self-control OR self-regulation OR behavior change)

These are starting queries, not a claim that they form an exhaustive systematic search. Adapt syntax to each provider and document every change.

## 3. Eligibility rules

### Include
- Peer-reviewed empirical studies, systematic reviews, and meta-analyses relevant to definitions, measurement, correlates, mechanisms, or interventions.
- Studies that directly measure a target construct or clearly explain why an adjacent construct is relevant.
- Human studies for claims about human outcomes.
- Theoretical papers only for mapping concepts; do not treat them as direct intervention evidence.

### Exclude or separately label
- Unsupported popular claims, motivational anecdotes, and commercial material as evidence of effectiveness.
- Studies whose construct or outcome is too ambiguous to interpret.
- Animal or computational studies from direct claims about human intervention outcomes; they may be noted separately as indirect evidence.
- Abstract-only records from detailed appraisal when full methods/results are necessary. Keep them in a “awaiting full text” queue instead of silently excluding or over-interpreting them.

Do not apply a date restriction initially. Record language and access restrictions, and disclose them as limitations.

## 4. Screening and source verification

For each discovered record:
1. Verify title, authors, year, DOI/PMID, journal, and record URL against PubMed, Crossref, or the publisher.
2. Identify publication type and whether it is a review, meta-analysis, randomized trial, observational study, qualitative study, or theoretical paper.
3. Retrieve the abstract and full text where legally and practically available. Do not infer missing methods or results.
4. Screen title/abstract, then full text when available; record include/exclude/uncertain plus a short reason.
5. Keep a source log with retrieval run ID, query, provider, date, record identifier, verification state, access level, and reviewer.
6. Treat retrieved metadata and abstracts as **unverified discovery material** until checked. Never promote a source to reviewed evidence merely because it was retrieved successfully.

## 5. Evidence extraction template

Extract only what the source explicitly supports:
- Citation and persistent identifier
- Study design and registration/protocol, if reported
- Population, sample size, setting, and relevant demographics
- Construct definition and operational measure
- Intervention/exposure and comparator
- Outcomes and follow-up period
- Effect estimate, uncertainty interval, and statistical details when reported
- Attrition, adherence, missing data, and adverse effects when reported
- Risk-of-bias concerns and key limitations
- Authors' conclusions, clearly separated from HDS interpretation
- Full-text availability and exact page/table/section supporting each extracted claim
- Reviewer, review date, and unresolved questions

Do not invent effect sizes, sample sizes, citations, or methodological details. If a paper does not report a field, record “not reported” or “not yet checked.”

## 6. Synthesis rules

- Separate **definition**, **measurement**, **correlation**, **prediction**, **mechanism**, and **causal intervention effect**.
- Do not infer causation from cross-sectional correlation.
- Do not treat statistically significant results as necessarily practically important.
- Prefer systematic reviews/meta-analyses for an overview, then inspect their methods and included studies; reviews can be outdated or flawed.
- Assess risk of bias and heterogeneity rather than counting positive studies.
- Distinguish direct evidence about self-discipline from indirect evidence about adjacent constructs.
- Report null, mixed, conflicting, and adverse findings as well as positive results.
- Do not pool effect estimates unless a defensible method and comparable outcomes support it.
- If evidence is insufficient, the correct result is “uncertain / insufficient evidence,” not a confident recommendation.

## 7. Claim labels

Every material statement in the final report must be assigned one of these labels:

- **FACT — source-supported:** accurately reflects a verified source, with a citation and location in the source.
- **INFERENCE:** reasoned interpretation derived from cited facts; show the reasoning and limitations.
- **HYPOTHESIS:** plausible but not established; state what evidence could test it.
- **OPINION / PRACTICAL SUGGESTION:** normative or pragmatic recommendation, explicitly not presented as established science.
- **UNKNOWN / CONFLICTED:** evidence is missing, inaccessible, inconsistent, or insufficient to resolve the claim.

A citation is necessary but not sufficient: the cited source must actually support the specific statement.

## 8. Deliverables and completion criteria

1. Search log and reproducible queries.
2. Deduplicated bibliography with DOI/PMID and verification status.
3. Screening log with reasons.
4. Evidence-extraction table.
5. Construct map distinguishing self-discipline from adjacent constructs.
6. Claim-evidence matrix with source locations, evidence type, confidence rationale, and contradictions.
7. Final report including scope, methods, findings, limitations, and unanswered questions.

The project must not be marked “research complete” until the search actually runs, source records are inspected, key claims are verified against source content, and an independent review is recorded. CI passing is a software quality signal, not scientific evidence.
