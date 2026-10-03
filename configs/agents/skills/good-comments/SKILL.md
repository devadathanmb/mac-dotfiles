---
name: good-comments
description: Use when adding, editing, reviewing, removing, or explaining Python comments or docstrings. Do not use for ordinary Python implementation changes without comment or docstring work.
---

# Good Comments

Optimize comments for first-pass understanding, not length or information density. A comment should make the code easier to understand after one read. Delete noise, but preserve enough context that the reader does not have to reconstruct the reason.

Read `references/examples.md` when the right comment or docstring shape is unclear or you are rewriting several comments. Read `references/python-docstrings.md` only when Python docstring layout matters.

## Core Test

Keep a comment when it explains something the code cannot make obvious:

- intent, rationale, trade-offs, rejected alternatives, or accepted limitations,
- a data shape or subgoal before or after a block,
- an invariant or business rule the block preserves,
- an edge case, external constraint, surprising behavior, or misuse hazard,
- the source, unit, or constraint behind a constant,
- what a later caller, parser, vendor, or framework expects,
- technical debt: what remains, why, and when it can be removed.

Remove or rewrite comments that:

- repeat visible code or control flow,
- restate variables without explaining their role,
- use ambiguous pronouns or generic nouns,
- compress familiar ideas into labels the reader must decode, such as `request fragments`, `value handling`, or `processing logic`,
- summarize every branch and intermediate value instead of stating the one useful reason or outcome,
- require the reader to cross-reference the prose with the code more than once,
- describe git history instead of current behavior.

## Plain Language

Give each comment one main job. State the fact that helps the reader most, then stop. Do not defensively encode every condition the code already shows.

Use the words the product, user, or external system uses. Prefer concrete terms such as `receipt`, `missing fields`, and the literal word or symbol being added over abstractions such as `request fragments`, `non-empty values`, and `separators`.

Write a natural sentence with a clear subject and verb. A precise comment does not need to sound formal or compressed. When two facts are both necessary, put them in separate sentences and present the cause before the consequence.

## Refactor Before Commenting

Prefer names, extraction, and type hints when they can carry the meaning.

Refactor when a comment only explains a bad name, narrates many lines step by step, or repeats in several places. Refactor first only when the change is local, safe, and within scope; otherwise preserve the invisible rationale in an accurate comment.

## Placement

Put a comment immediately before the block it explains. Place branch rationale above the relevant `if` or `elif`. Use inline comments only for small local surprises.

Do not name the helper on the next line. Explain the non-obvious outcome, precondition, or reason.

## Summary and Complex Flow

Use a summary comment before a coherent block when its subgoal is not apparent line by line. State the block's result or role, not its mechanics. Several summaries may outline a long function before the reader studies each block.

Do not extract a block solely to eliminate useful navigation. Extract it when the block is independently coherent and the new name makes the flow easier to follow.

When data passes through several shapes, comment where a reader would otherwise pause. Explain the non-obvious reason for keeping an extra shape or stage; do not narrate every transformation.

## Test Flow Comments

Use numbered `Step N:` comments only when a test has several dependent phases whose order is difficult to follow. Simple API, schema, query, and single-action tests should read linearly without procedural labels.

Name the non-obvious state, invariant, or transition. Remove labels such as `Call the API`, `Create the record`, or `Assert the result` when the following line says the same thing.

## Precision

Name the exact subject instead of making the reader resolve `this`, `it`, or `they`. State units, boundaries, inclusivity, ordering, failure behavior, and side effects when they affect the contract.

Use a compact input/output example, mapping, or diagram when it communicates an edge case or data shape faster than prose. Prefer familiar, exact words over compact terminology.

## Docstrings

Use a function docstring when callers need a contract that names and type hints cannot express: output shape, ordering, side effects, supported edge cases, exceptions, or parser and framework behavior.

Use a module or class docstring when readers need its role, entry points, data flow, ownership boundaries, or interaction model before reading individual functions.

Do not add a docstring merely because code is new. For a private helper with one obvious caller, prefer comments at the caller and inside tricky branches.

## Maintenance

When behavior changes, verify nearby comments and docstrings against the new code. Update or remove stale rationale, invariants, examples, constraints, and debt notes in the same change.

## Final Pass

Read the code as if you have no prior context. Ask:

- Can I understand the comment and block together on the first pass?
- Does the comment reduce the time needed to understand the block, or does it add another sentence to decode?
- Does it preserve non-obvious, still-correct information?
- Is it next to the code it explains?
- Would a local rename or extraction carry the meaning better?
- Did nearby behavior change make it stale?

Short but vague is bad. Longer is fine only when each sentence removes real ambiguity. If the comment restates the whole block in denser language, simplify it to the one reason or outcome the code cannot show.
