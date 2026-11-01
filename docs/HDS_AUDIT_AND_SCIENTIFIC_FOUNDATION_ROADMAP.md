# HDS Repository Audit and Scientific Foundation Roadmap

**Status:** Initial repository-level audit  
**Date:** 2026-11-01  
**Branch:** feature/hds-scientific-foundation-roadmap  
**Scope:** Read-only inspection of the default-branch README, application entry point, requirements, and the backup/recovery runbook. This is not a full code audit, security assessment, or executed test report.

## 1. Executive assessment

The repository already contains a substantial **HDS Company OS software foundation**. The README describes persistent company state, a 17-agent registry, project-scoped permissions, bounded autonomous research, evidence/claim/knowledge workflows, founder intelligence, approvals, failure/recovery controls, scientific provenance, PostgreSQL support, observability, rate limiting, and production-oriented container definitions.

The application entry point imports and exposes a broad set of research, measurement, assessment, training, challenge, safety, competition, and company-analytics services. This indicates that the project is not starting from zero.

However, the existence of code, database models, API routes, or AI agents does not establish that a scientific institute exists operationally, that research outputs are valid, that interventions work, or that the application is production-secure. Those require separate implementation reviews, tests, real research protocols, human expertise, and independent evidence.

**Core recommendation:** preserve the Company OS as the operational platform, but make the scientific foundation explicit and authoritative. HDS should be designed as both (1) an emerging scientific/academic field and (2) an organization/company that researches, develops, educates, trains, measures, and applies human development.

## 2. What is evidenced in the inspected repository

### 2.1 Company OS and AI orchestration

The README describes:
- Persistent company state and a 17-agent registry.
- Project-scoped permissions.
- Bounded autonomous research and founder intelligence.
- Task execution with permission checks, model-call audit logging, evaluation, failure capture, lessons, replanning, and decision gates.
- Human approvals for selected high-risk or low-confidence decisions.
- A unified Founder OS dashboard.

These are repository-described capabilities. Their end-to-end behavior and reliability were not verified in this audit.

### 2.2 Research and scientific data structures

The application entry point imports or references services for research cycles, study execution, scientific registries, scientific AI guardrails, measurement registries, claim-state management, scientific analysis, and assessment.

The API definitions include requests for research questions, study participants, study outcomes, hypotheses, constructs, measures, interventions, and synthesis with limitations and uncertainty.

This is a useful foundation for a research workflow. It does not by itself demonstrate that the system can discover literature comprehensively, evaluate risk of bias, conduct valid statistical analyses, validate measures, or independently establish causal effects.

### 2.3 Human-development application layer

The inspected application entry point includes routes or service integrations for:
- HDS programs and challenges.
- Competitions and participant safety status.
- Assessment constructs, measures, sessions, observations, and progress.
- Training protocols and progression.
- Adaptive training recommendations and applications.
- Challenge execution, stop controls, and emergency-stop operations.
- Research-loop creation and execution.
- Project-level company analytics.

This indicates a broad application concept spanning assessment, training, challenges, safety, research, and organizational management.

### 2.4 Operations and infrastructure

The README and backup runbook describe PostgreSQL support, production identity-signing enforcement, governed code-change proposals, approval/verification/rollback, safety governance, Docker/Compose definitions, health checks, structured observability, rate limiting, and backup/restore tooling.

The README also explicitly lists production dependencies that remain operator responsibilities: an authenticated identity provider or proxy, secret management, external encrypted backup storage and retention, distributed rate limiting/observability for horizontal scale, and an isolated worker/VM for autonomous code execution.

These are important caveats. A production-ready claim should not be made until these dependencies are configured and tested in the actual deployment environment.

## 3. What remains unverified

This audit did not execute the application, run the test suite, inspect every module, inspect every migration, validate the agent registry, or perform penetration/security testing. Therefore the following remain unverified:
- Whether all documented features work end-to-end.
- Whether all tests pass and whether test coverage is adequate.
- Whether authorization is consistently enforced across every endpoint and data access path.
- Whether autonomous execution is isolated safely in the deployed environment.
- Whether scientific retrieval is available; the README says the current local provider is a safe placeholder and does not provide external scientific retrieval.
- Whether literature synthesis, evidence grading, and statistical analysis are methodologically valid.
- Whether measurement instruments have reliability, validity, fairness, and measurement-invariance evidence.
- Whether any HDS intervention has demonstrated efficacy, transfer to real life, or retention.
- Whether any academic institution recognizes HDS as a formal academic discipline or awards an HDS degree.
- Whether the current framework document on the previously used feature branch is present in the default branch. It was not found at the expected path on the default branch during this audit.

## 4. Strategic architecture: two identities, one coherent system

### A. HDS as a scientific and academic field

The field should develop a coherent research agenda around human capabilities and their development across the lifespan and across three contexts:
1. The self.
2. The world/environment.
3. Other people.

Mental development is the central research priority. Physical-motor development, hybrid performance, social capabilities, practical/environmental competence, values, and education are integral domains.

HDS should integrate existing disciplines rather than claim that psychology, cognitive science, education, neuroscience, or exercise science do not already study these topics. Its academic distinctiveness must be demonstrated through clear constructs, useful synthesis, valid methods, cumulative findings, and independent scholarly contribution.

### B. HDS as a company and institution

The organization should translate reliable knowledge into:
- A prestigious, scientifically independent research institute.
- Education programs for children, adolescents, adults, and lifelong learners.
- Development centers and individual/group programs.
- Hybrid physical-development and performance programs.
- Professional academies and demanding coach qualifications.
- Assessments, challenges, and competitions.
- Organizational, educational, community, and institutional partnerships.
- Research collaborations and international activity.

The company can lead and invest in the field, but it cannot declare its own academic recognition or control scientific conclusions. Research governance must protect independence from commercial pressure.

## 5. Scientific governance requirements

The Research Institute should be the scientific authority for HDS methods and claims. It should be able to restrict, pause, or discontinue a program when evidence or safety requires it.

Every research or development initiative should record:
1. Target capability and operational definition.
2. Theoretical rationale and proposed mechanism, distinguishing evidence from hypothesis.
3. Literature search strategy, inclusion/exclusion criteria, and evidence limitations.
4. Target population and suitability.
5. Intervention protocol, dose, progression, instructor requirements, and comparison condition where appropriate.
6. Risks, contraindications, safeguarding, informed consent, and stop criteria.
7. Outcomes, validated measures, analysis plan, and missing-data approach.
8. Results, adverse events, uncertainty, limitations, and conflicts of interest.
9. Transfer to untrained tasks/real-world settings.
10. Retention and follow-up.

HDS must distinguish task performance, closely related capability, transfer to everyday life, and retention over time. No single test should be treated as a complete measure of a person's worth or character.

Research involving people requires appropriate ethics review, informed consent, privacy protection, safeguarding, and compliance with applicable law. Clinical diagnosis and treatment must remain with appropriately licensed professionals.

## 6. Priority roadmap

### Phase 0 — Establish a reliable baseline
- Inventory every repository file, module, migration, API route, agent, workflow, test, and deployment artifact.
- Run the existing automated tests in a safe environment and record the exact result.
- Map the application architecture and dependencies.
- Review authentication, authorization, project isolation, audit trails, secrets handling, data retention, and autonomous execution boundaries.
- Classify each feature as implemented and tested, implemented but unverified, partial, prototype, documented only, or missing.

**Exit criteria:** a reproducible technical inventory, test report, architecture map, and prioritized risk register.

### Phase 1 — Establish HDS scientific foundations
- Publish the HDS mission, scope, terminology, and three-layer framework.
- Build the HDS domain taxonomy and a capability ontology.
- Define the mental-capability map as the first major scientific program.
- Create a research protocol template, evidence-review standard, claim registry policy, measurement-development standard, and human-research ethics workflow.
- Establish independent scientific review and conflict-of-interest policies.

**Exit criteria:** every proposed HDS capability and method can be traced to a definition, evidence status, and research plan.

### Phase 2 — Build the first research program
- Select a narrow, important, researchable mental capability (self-regulation is a possible candidate, not a pre-decided answer).
- Conduct a systematic or appropriately scoped evidence review.
- Define constructs and competing explanations.
- Identify existing validated instruments before creating new ones.
- Design a feasible, ethical pilot protocol with qualified scientific supervision.
- Preregister where appropriate and specify analysis and stopping rules.
- Publish findings and limitations, including null or negative results.

**Exit criteria:** a transparent research dossier and an ethically approved study plan; no efficacy claims before suitable results exist.

### Phase 3 — Build and test the first education and development programs
- Translate only appropriately supported findings into a small pilot curriculum.
- Create distinct mental, physical/hybrid, social, and practical modules.
- Train and supervise qualified instructors.
- Measure baseline, immediate outcomes, transfer, safety, and follow-up retention.
- Adapt for age, disability, culture, health status, and participant goals.

**Exit criteria:** feasibility and safety demonstrated, with transparent outcome data and limitations.

### Phase 4 — Build the professional academy
- Define common core competencies and specialist tracks.
- Establish selective, fair admission criteria.
- Require scientific literacy, practical skill, teaching/coaching performance, supervised practice, ethics, safety, and scope-of-practice examinations.
- Maintain continuing education, reassessment, complaints, and certification review.
- Never imply clinical or regulated credentials that have not been separately obtained.

**Exit criteria:** competency standards and assessment rubrics independently reviewed and piloted.

### Phase 5 — Institutional and academic partnerships
- Collaborate with universities, schools, healthcare and rehabilitation professionals, sports organizations, employers, and public institutions.
- Pursue peer-reviewed publication, external replication, conferences, and collaborative research.
- Develop formal university degree pathways only with qualified academic partners and applicable accreditation.
- Scale commercial services only where evidence, staff capacity, safety, and demonstrated value support expansion.

**Exit criteria:** independently evaluated partnerships and a sustainable model that does not compromise research independence.

## 7. Recommended changes to Company OS

The software should support the scientific governance model rather than letting autonomous agents define it. Priorities:
- A canonical capability/domain registry linked to constructs, measures, interventions, studies, programs, and claims.
- Evidence records with source provenance, review status, date, population, design, limitations, and conflict disclosures.
- Explicit claim states: unassessed, hypothesis, preliminary, supported with limitations, replicated, contradicted, retired.
- Versioned research protocols and analysis plans.
- Human approval gates for protocol changes, human-subject research, safety-sensitive interventions, publication claims, and external actions.
- Separation of AI-generated suggestions from human-reviewed scientific decisions.
- Immutable or tamper-evident audit history for critical scientific and safety decisions.
- Role-based access and privacy-by-design for participant data.
- A research dashboard that surfaces evidence gaps, overdue reviews, safety events, protocol deviations, and follow-up completion.
- No autonomous agent should approve its own high-risk scientific claims or human-subject protocols.

## 8. Immediate next actions

1. Complete the full repository inventory and run tests; do not infer quality from README descriptions.
2. Produce a module-by-module technical status report and security/risk register.
3. Create a canonical HDS scientific foundation document set: mission and scope, domain taxonomy, capability ontology, research standards, measurement standards, and governance.
4. Choose the first research question only after mapping existing evidence and candidate constructs.
5. Keep the research institute scientifically independent from commercial and founder pressure.
6. Continue development on a dedicated feature branch. Do not merge to main, deploy, publish, or incur paid costs without explicit authorization.

## 9. Audit conclusion

The current repository appears to be a substantial early software platform for operating an AI-enabled HDS organization, with research and human-development workflows represented in its architecture. The next challenge is not simply adding more AI agents or endpoints. It is making the scientific model explicit, independently governed, testable, and operational—and then aligning the software, education, professional academy, physical/hybrid development, and company strategy around that model.

**HDS should grow into a major company by creating demonstrable value, and into a credible academic field through sustained independent scientific contribution. These are related ambitions, but they require different forms of proof.**


## 10. The knowledge–capability–performance gap

### 10.1 Foundational proposition

A central HDS proposition is that **knowing what to do is not the same as being able to do it, and being able to do it is not the same as consistently doing it in real life**.

Modern societies have extensive access to information. Formal education often measures knowledge through tests, grades, and academic achievement. Those are meaningful but incomplete outcomes. People also need the capabilities to apply knowledge, regulate behavior, make decisions, resist or manage temptations, adapt to changing circumstances, and act effectively in everyday life.

HDS should investigate and develop this missing bridge between knowledge and effective action.

### 10.2 A three-part distinction

1. **Knowledge:** what a person knows, understands, remembers, and can explain.
2. **Capability:** what a person can reliably do or learn to do under defined conditions.
3. **Performance:** what the person actually does in a particular situation, at a particular time, with particular resources and constraints.

Example: a person may know that saving money is beneficial, understand budgeting, and still spend impulsively. This does not automatically prove a lack of knowledge or a fixed personal weakness. It may involve impulse regulation, delayed gratification, planning, financial stress, habit, social influence, environmental design, or limited resources.

### 10.3 Initial failure-analysis model — hypotheses, not an established exhaustive theory

When a person does not achieve an intended outcome, HDS should investigate multiple possible contributors rather than label the person weak.

Candidate contributors include:
- **Knowledge gap:** missing or inaccurate information, misunderstanding, poor procedural knowledge.
- **Capability gap:** a skill, cognitive, emotional, physical, social, or practical capability is insufficiently developed for the task.
- **Motivation and goal conflict:** competing goals, low value, ambivalence, fatigue, or short-term reward dominance.
- **Execution and regulation gap:** difficulty initiating, planning, inhibiting impulses, maintaining attention, or recovering after interruption.
- **Context and opportunity constraints:** poverty, time pressure, unsafe environments, inaccessible systems, social pressure, lack of tools or support.
- **Health and capacity constraints:** illness, disability, sleep deprivation, stress, pain, or other factors that affect functioning.
- **Task-design mismatch:** the demand exceeds current capacity, instructions are unclear, or the task is poorly structured.
- **Learning and feedback failure:** insufficient practice, feedback, reinforcement, adaptation, or opportunity to transfer learning.

These categories are an initial diagnostic framework for research and program design. They may overlap, interact, and vary by person and context. They must be operationalized and tested rather than treated as settled scientific categories.

### 10.4 HDS development objective

HDS should not stop at transmitting information. It should ask:
- What does the person need to know?
- What must the person be able to do?
- Under which conditions must the capability work?
- What practice, instruction, feedback, support, and environmental changes are needed?
- Can the person apply the capability outside the training setting?
- Does the capability persist over time?
- What barriers are not reasonably attributable to the individual?

The goal is not to make every person conform to one ideal. It is to help people develop meaningful capabilities, autonomy, functioning, and the ability to pursue their own legitimate goals.

### 10.5 Relationship to education

HDS should complement and improve education, not dismiss knowledge or academic learning. Knowledge is essential; it is simply not sufficient for every life outcome.

A fuller educational model should connect:
- Knowledge and understanding.
- Practiced skills and capabilities.
- Application in realistic contexts.
- Reflection, feedback, and self-correction.
- Social and practical learning.
- Physical literacy and health.
- Values, responsibility, and ethical judgment.
- Lifelong learning and adaptation.

Grades can measure selected academic outcomes. They should not be treated as a complete measure of a person's capabilities, character, potential, or readiness for life.

### 10.6 Research questions

This proposition creates a foundational HDS research program:
1. How should knowledge, capability, and performance be distinguished and measured?
2. Which factors best explain the gap between intention, knowledge, capability, and action in different domains?
3. How do self-regulation, habits, executive functions, emotion, motivation, and context interact?
4. Which forms of practice improve performance beyond the training environment?
5. How can education develop both understanding and the capability to apply what is learned?
6. Which barriers require individual development, and which require environmental or institutional change?
7. How can capability development be measured fairly across age, disability, culture, and different life circumstances?

**Scientific caution:** the statement that many failures arise from insufficient knowledge or insufficient capability is a useful starting hypothesis, not a universal law. HDS must test it against competing explanations and avoid turning structural barriers or health limitations into moral judgments about individuals.
