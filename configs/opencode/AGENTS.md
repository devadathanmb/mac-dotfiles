## Efficient Execution

- Batch independent tool calls and keep their output narrowly filtered.
- Inspect only relevant files and ranges; avoid repeated or repository-wide reads.
- Make the smallest correct change, preferably in one implementation pass.
- Use local code and documentation before searching the web.
- Run one verification proportional to the change; expand only after a specific failure.
- Diagnose failures from the exact error instead of retrying broadly.
- Avoid throwaway scripts when normal project commands can verify behavior.
- Ask only when ambiguity would materially change behavior; otherwise proceed.
