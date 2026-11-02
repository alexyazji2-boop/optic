<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

OPTIC — AUTONOMOUS OVERNIGHT EXECUTION CONTROLLER
The Optic engineering directives and Phase 01–11 prompts have been saved in the repository.
Locate and read those files in numerical order.
Follow the master engineering rules.
Your assignment is to execute the phases sequentially and autonomously.
Execution rules

1. Never skip a phase.
2. Read the full phase instructions before implementing.
3. Complete the applicable changes and verification before moving to the next phase.
4. Do not mark a phase complete solely because the code compiles.
5. Do not suppress tests or warnings to manufacture success.
6. Maintain persistent progress after every meaningful milestone.
7. Commit coherent, verified local changes.
8. Record blockers and continue independent safe work where possible.
9. Do not deploy to production.
10. Do not perform destructive operations or external account changes without authorization.

Context preservation
Before a major context compaction or phase transition, update:
docs/post-demo-ultra/PROGRESS.md
Include:

* Current phase.
* Completed requirements.
* Incomplete requirements.
* Files changed.
* Tests passed.
* Tests failed.
* Known bugs.
* Git commit hash.
* Next action.

On resumption, read PROGRESS.md and REQUIREMENTS_MATRIX.md before making changes.
Do not duplicate completed work unnecessarily.
Parallel work
You may use independent subagents for narrowly scoped, read-only audits or isolated tests when supported.
Do not allow multiple agents to make conflicting changes to the same files.
Do not parallelize phases that depend on unfinished prior phases.
Preserve a single authoritative implementation and requirements record.
Resource discipline
Use existing providers, test frameworks, and infrastructure wherever possible.
Avoid unnecessary API calls.
Do not introduce paid tools or services without approval.
If available context, execution limits, permissions, or quotas prevent further progress, save a complete checkpoint and report the blocker.
Do not claim that work continued after execution stopped.
Final requirement
Continue through all phases as resources and permissions allow.
Maintain rigorous testing.
Prioritize simplicity, correctness, financial-data integrity, and Milo reliability.
Produce the complete final QA report.
Do not deploy.
Begin with the earliest incomplete phase.
