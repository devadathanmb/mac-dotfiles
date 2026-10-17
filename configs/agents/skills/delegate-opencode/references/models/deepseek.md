# deepseek-v4.1-flash

Fast and accurate on well-specified mechanical changes: renames across files, moving code verbatim,
applying a rename table, CSS selector changes, extracting a helper from given call sites. Open
design decisions get shallow answers.

## Prompting

- Spell out every step and target: files, names, rename tables (old → new), where each block moves,
  and what must stay byte-identical.
- Make acceptance commands exact (word-bounded `rg` patterns); it checks them literally.
- When behavior can't be unit-tested in its environment, say how to verify it; otherwise it writes a
  test that only echoes its own configuration.

## Check on review

- Tautological tests; drop them and verify the behavior directly.
- Small duplication, such as one value defined twice in CSS or constants.
- With every step written out (exact functions to add, expressions to move, acceptance greps), it
  lands one clean commit with no deviations. It may still leave a scratch log under `/tmp`; check the
  report's deviations section.
