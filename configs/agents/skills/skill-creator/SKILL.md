---
name: skill-creator
description: Create or improve concise, agent-agnostic Agent Skills. Use when the user asks to create, rewrite, reorganize, or improve a skill or its trigger description.
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Skill Creator

Create the smallest skill that reliably changes agent behavior. Every token
competes with the task, conversation, and other instructions for context.

## Workflow

1. Extract the intended capability, expected inputs, output contract, trigger
   conditions, exclusions, non-negotiable rules, and target environment.
2. Ask only for missing decisions that materially change behavior. If user
   notes conflict about a requirement, default, fallback, or optionality,
   follow established precedence; if none exists, ask one focused question
   instead of choosing an interpretation.
3. For an existing skill, read its complete `SKILL.md` and every bundled
   resource, including unreferenced files, before proposing changes.
4. Inspect neighboring skills for overlapping triggers, duplicated ownership,
   or conflicting rules. Change boundaries only when the overlap is real.
5. Research authoritative documentation, repository behavior, domain terms,
   and established workflows before encoding them. Delegate independent
   research when useful, then curate the findings.
6. Distinguish deliberate policy from accidental wording. For an existing
   skill, create the preservation ledger described below before editing.
7. Design the smallest file structure that supports the capability. Prefer one
   `SKILL.md`; add resources only when they save loaded context or provide
   necessary deterministic behavior.
8. For a material rewrite, show the proposed structure, semantic changes,
   removals, and preserved rules unless the user authorized direct work.
9. Write the smallest coherent change, restructuring only as far as needed to
   integrate it across the complete skill, then perform the final review below.

## Context Standard

Keep a sentence only when it does at least one of these:

- Changes agent behavior.
- Defines a decision or constraint.
- Routes the agent to required context.
- Prevents a demonstrated failure.
- Provides information the agent cannot reliably infer.

Remove motivational prose, reassurance, repeated summaries, generic knowledge,
conversational filler, and instructions that merely sound thorough.

Measure concision by unique behavior-bearing content, not line count. Rewrapping
or rephrasing the same information is not a reduction.

Write for an agent starting a fresh chat: state current behavior directly, not
how the skill used to work or why it changed. Mention an unwanted behavior only
when naming it prevents a realistic, recurring failure. Do not introduce
irrelevant terms that may bias later output.

Scope instructions to the decision they govern. When defining when to use an
approach, specify its trigger without prescribing alternatives already governed
elsewhere. Check that the wording does not unintentionally redirect adjacent
behavior.

Use `must`, `always`, `never`, and `only` when the rule is deliberately
absolute. Preserve the user's intended rule strength.

Match specificity to failure cost. Use principles when several approaches are
valid, explicit sequences when order matters, and scripts when determinism or
repeatability is required.

Include a command only when its output changes a decision or it performs a
required action. Do not accumulate diagnostics merely because they may help.

Keep each rule in one canonical location and route to it instead of restating
it.

## Editing Existing Skills

Treat the current skill, its examples, and user feedback as evidence. Distill
rough notes into rules without copying incidental wording.

Before editing, record a preservation ledger covering:

- Trigger conditions and exclusions.
- Required output structure, exact literals, defaults, and fallbacks.
- Optional versus mandatory behavior.
- Source-of-truth, mutation, confirmation, and safety rules.
- Edge cases and examples that prevent demonstrated failures.

Account for every existing rule as preserved, rephrased, moved, corrected, or
removed. Treat unexplained template values and fallbacks as potentially
operational; ask before changing them. Never lose information silently.

A request to shorten, reorganize, or improve a skill does not authorize changed
semantics. Keep behavior corrections separate from compression, and preserve
deliberate opinionated rules even when alternatives exist.

Treat every behavior change as section-level reconciliation, never a local
insertion:

1. Trace the concept through the complete skill and its resources, including
   differently worded rules, examples, and adjacent sections.
2. Choose one canonical owning section for the behavior.
3. Rewrite or reorder that section as a coherent unit. Do not append a bullet
   when the new rule changes, qualifies, or overlaps existing guidance.
4. Search the complete result for the concept again and reconcile stale,
   duplicated, or contradictory statements before validating.

The smallest correct edit is the smallest coherent edit, not the smallest
patch. Move, merge, rename, or remove affected material as needed, but do not
restructure unrelated sections without reason.

Correct proven contradictions and broken examples, but do not manufacture gaps
to justify a rewrite. After editing, compare the complete result with the
preservation ledger; structural validation does not prove semantic preservation.

## Metadata

Use portable Agent Skills frontmatter:

```markdown
---
name: concise-skill-name
description: Performs a specific capability. Use when the user asks for the relevant tasks, artifacts, or workflows.
---
```

- `name` is lowercase, hyphen-separated, 1-64 characters, and matches the
  parent directory.
- `description` states what the skill does and when it should trigger.
- Include concrete user language and near-synonyms that improve discovery.
- Add exclusions only when they prevent realistic over-triggering.
- Add `compatibility` only when runtime, package, network, or environment
  requirements affect execution.
- Do not repeat trigger guidance in the body; the body loads after selection.

## Structure

```text
skill-name/
|-- SKILL.md
|-- references/  # optional domain knowledge loaded when needed
|-- scripts/     # optional deterministic or repeated operations
`-- assets/      # optional output materials
```

A skill that must stay out of version control is named `private-<name>` (directory and `name` field both); the skills directory gitignores that prefix.

Keep the operating workflow and decisions in `SKILL.md`. Move detailed domain
knowledge into focused references only when selective loading saves context.

Link every resource from `SKILL.md` and state when to read or run it. Keep
references one level deep and avoid chains of references.

Do not create a resource merely because the format permits it. One clear
Markdown file is the default. When a script is justified, make it self-contained
or declare dependencies, validate inputs, and design its output for an agent
reader:

- Print only what the agent needs to act on. Small results print inline.
- Cap large output. Show a short preview, write the full output to a temporary
  file, and end with one line giving the file path and size so the agent can
  `rg` or read just the part it needs instead of re-running with a larger cap.
- Report errors as one line on stderr with a hint for the next step, and use a
  nonzero exit code. No stack traces or progress noise.
- Make flags order-independent and defaults safe; keep help text short.
- Do not build background or job handling into the script. Only the harness can
  notify the agent when a task finishes, so have the skill tell the agent to use
  the harness's background-task feature for slow commands.
- Cache or deduplicate repeated expensive calls when results are stable.

## Examples

Add an example only when it clarifies a judgment, format, edge case, or workflow
that prose cannot communicate as well. For output-generating skills, prefer one
complete, high-quality example over several partial templates.

Use concise, generic examples built from the target environment's real
abstractions. Do not copy incidental product code into a general rule.

Make every example obey every rule. Examples demonstrate the contract but do
not replace it. Remove examples that only restate obvious syntax.

## Final Review

- Read the complete final skill, not only the changed section or diff.
- Compare it with the preservation ledger, including exact literals, defaults,
  fallbacks, optionality, and rule strength.
- Remove duplicate rules, stale paths, unsupported claims, and unused resources.
- Confirm every command changes a decision or performs a required action.
- Confirm every reference exists and every example supports its rule.
- Confirm the description triggers intended requests without claiming adjacent
  work.
- If reduction was a goal, confirm behavior-bearing content was removed or
  consolidated rather than merely rewrapped.
- Run the available Markdown formatter and
  `scripts/validate_skill.sh <skill-directory>`. It validates structure and
  frontmatter, not semantics.
- Tell the user what changed, what was deliberately preserved, and any
  unresolved decision.
