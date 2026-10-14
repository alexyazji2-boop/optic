"""Optic Desk's daily edition: evidence, outline, draft, checks, render.

See docs/desk/EDITORIAL-SPEC.md for what an edition is and why each stage
exists. The stages, in order:

  evidence.gather   every fact the edition may use, each with its source,
                    publication time, event time and the period it describes
  outline.build     deterministic: which story leads, which numbers matter,
                    which relationships to evaluate and what bears on each
  ai.write_edition  the prose, written from the outline and nothing else
  check.run         every number, citation, unit and date checked against the
                    evidence before an edition is kept
  edition.publish   one canonical edition per date and slot, claimed on disk
"""
