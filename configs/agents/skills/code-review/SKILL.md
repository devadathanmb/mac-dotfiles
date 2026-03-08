---
name: code-review
description: Use when reviewing code changes, pull requests, or implementations - performs holistic senior/principal engineer review focusing on code quality (naming, readability, abstractions, DRY, SOLID), business logic correctness with edge case analysis, and best practices without over-engineering
---

# Code Review

## Overview

Code reviews should catch bugs before they reach production, ensure maintainability, and uphold quality standards. A thorough review requires understanding not just the code but its context: related models, database constraints, business logic, and potential edge cases.

**Core principle:** Review holistically like a senior principal engineer—focus on correctness, readability, and maintainability without over-engineering.

**Violating the letter of this process is violating the spirit of code review.**

## When to Use

Use this skill for:
- Pull request reviews
- Code implementation reviews
- Pre-merge quality checks
- Architecture validation

**Use this ESPECIALLY when:**
- Code modifies critical paths (authentication, payments, data integrity)
- Changes affect database schema or constraints
- Business logic is complex or has edge cases
- Code uses unfamiliar libraries or methods
- Multiple systems interact

## The Review Framework

You MUST complete each phase before approving.

### Phase 1: Context Gathering

**BEFORE reviewing code:**

1. **Understand the Problem**
   - What is this change trying to accomplish?
   - What is the business requirement or bug being fixed?
   - Read the PR description, issue, or ticket completely

2. **Map the Impact Surface**
   - What models/entities does this modify?
   - What database tables are affected?
   - What API endpoints are touched?
   - What other services interact with this?

3. **Gather Related Resources**
   - View model definitions
   - Check database schema, constraints, indexes
   - Review column types, default values, nullable fields
   - Examine related business logic in other files
   - Check API contracts or interfaces

4. **Verify Unknown Methods/Libraries**
   - For any library or method outside your reliable knowledge:
     - **REQUIRED:** Use Context7 MCP first for library documentation
     - If Context7 doesn't have it, use web search for official docs
   - Read method signatures, parameters, return types
   - Understand side effects, error cases
   - **NEVER approve code using methods you don't fully understand**

### Phase 2: Code Quality Review

**Focus on readability and maintainability:**

1. **Naming Clarity**
   ```
   ✅ GOOD:
   - Names explicitly communicate purpose
   - Can be verbose if needed for clarity
   - Reader understands intent without context
   
   ❌ BAD:
   - Cryptic abbreviations (usr, tmp, dat)
   - Generic names (data, info, handler, manager)
   - Misleading names (doesn't match actual behavior)
   ```

2. **Natural Readability**
   - Does code read like prose?
   - Can you follow the logic flow easily?
   - Are complex sections abstracted appropriately?
   - Is the happy path clear?
   - **Primary goal:** Code should be self-documenting

3. **Abstraction Balance**
   ```
   Extract to method when:
   - Logic pollutes public methods
   - Same pattern repeats (DRY)
   - Complex logic obscures main flow
   - Nested conditions exceed 2-3 levels
   
   DON'T extract when:
   - Logic is simple and contextual
   - Abstraction adds indirection without clarity
   - Used only once and already clear
   ```

4. **SOLID Principles (Where Applicable)**
   - **Single Responsibility:** Each method/class has one clear purpose
   - **Open/Closed:** Extensible without modification
   - **Liskov Substitution:** Subtypes work as expected
   - **Interface Segregation:** No forcing unused methods
   - **Dependency Inversion:** Depend on abstractions, not concretions
   
   **NOTE:** Not all principles apply in every codebase. Apply where they improve the code, not dogmatically.

### Phase 3: Business Logic & Correctness Review

**Most critical phase—edge cases cause production bugs:**

1. **Trace Data Flow**
   - Where does input originate?
   - How is it transformed?
   - Where is it stored/used?
   - What validations exist?
   
   **REQUIRED SUB-SKILL:** Use systematic-debugging for complex data flow analysis

2. **Identify Edge Cases**
   
   **Database operations:**
   - What if record doesn't exist?
   - What if multiple records match?
   - What if NULL/empty values?
   - What about default values?
   - Are constraints (UNIQUE, NOT NULL, FK) respected?
   - Does index exist for query performance?
   
   **Collections/Lists:**
   - What if empty?
   - What if single item?
   - What if very large?
   - What about duplicates?
   
   **Strings:**
   - What if empty string vs null?
   - What about whitespace?
   - What about very long strings?
   - What about special characters?
   
   **Numbers:**
   - What if zero?
   - What if negative?
   - What about integer overflow?
   - What about division by zero?
   
   **Time/Dates:**
   - What about timezone handling?
   - What about DST transitions?
   - What about leap years/seconds?
   - What about date boundaries?
   
   **Concurrency:**
   - What if two requests modify same data?
   - Are there race conditions?
   - Is locking needed?
   - What about transaction boundaries?

3. **Validate Against Constraints**
   
   **For each database write:**
   - Check model definition for constraints
   - Verify NOT NULL columns have values
   - Verify UNIQUE constraints won't be violated
   - Check foreign key relationships exist
   - Confirm data types match schema
   - Verify default values are appropriate
   
   **For each database read:**
   - Check if NULL handling is needed
   - Verify joins are correct
   - Check if indexes support query
   - Confirm eager/lazy loading is appropriate

4. **Security Review**
   - Are inputs validated?
   - Is output properly escaped?
   - Are permissions checked?
   - Is authentication verified?
   - Are secrets properly handled?
   - Is SQL injection prevented?
   - Is XSS prevented?

5. **Error Handling**
   - Are errors caught appropriately?
   - Are error messages helpful?
   - Is logging sufficient for debugging?
   - Are transactions rolled back on error?
   - Is cleanup performed?

### Phase 4: Validation Strategy

**Use defense-in-depth pattern:**

After identifying potential edge cases, ensure validation exists at multiple layers:

1. **Entry Point Validation**
   - API/Controller level checks
   - Type validation
   - Basic sanity checks

2. **Business Logic Validation**
   - Domain-specific rules
   - State consistency checks
   - Business constraint verification

3. **Data Layer Validation**
   - Database constraints
   - Model validations
   - Schema enforcement

**REQUIRED SUB-SKILL:** Use defense-in-depth when suggesting validation improvements

### Phase 5: Testing Verification

**Ensure changes are properly tested:**

1. **Test Coverage**
   - Are happy paths tested?
   - Are edge cases tested?
   - Are error cases tested?
   - Are integration points tested?

2. **Test Quality**
   - Do tests verify behavior, not implementation?
   - Are tests isolated and independent?
   - Are test names descriptive?
   - Do tests actually assert the right things?

3. **Missing Tests**
   - Identify untested edge cases
   - Suggest specific test scenarios
   - Highlight risky areas without tests

## Review Checklist

Use this before approving:

**Context:**
- [ ] Understand what problem this solves
- [ ] Reviewed related models/schemas
- [ ] Checked database constraints and columns
- [ ] Verified unfamiliar methods/libraries with Context7 or docs

**Code Quality:**
- [ ] Names are clear and communicate intent
- [ ] Code reads naturally without mental gymnastics
- [ ] Complex logic appropriately abstracted
- [ ] DRY principle followed where appropriate
- [ ] SOLID principles applied where applicable
- [ ] No over-engineering or unnecessary complexity

**Business Logic:**
- [ ] Data flow is clear and correct
- [ ] All edge cases identified and handled
- [ ] Database constraints respected
- [ ] NULL/empty values handled
- [ ] Concurrency issues considered
- [ ] Security implications reviewed
- [ ] Error handling is appropriate

**Testing:**
- [ ] Tests exist for new/changed functionality
- [ ] Edge cases are tested
- [ ] Error cases are tested
- [ ] Test quality is good

## Red Flags - Request Changes

If you see these, DO NOT approve:

- **Unknown methods/libraries used without verification**
- "I'll fix that later" comments in code
- Missing NULL checks on nullable fields
- No validation on user input
- Hard-coded values that should be configuration
- Database operations without transaction handling
- Commented-out code blocks
- Missing error handling
- No tests for critical logic
- Complex logic without abstraction
- Names that don't match behavior
- Copy-pasted code instead of DRY
- Tight coupling that should be abstracted
- Missing edge case handling
- Security vulnerabilities

## Common Mistakes in Reviews

| Mistake | Better Approach |
|---------|----------------|
| Approve without reading related code | Always gather context first |
| Focus only on style | Correctness and business logic first |
| Miss edge cases | Systematically check all edge case categories |
| Accept "it works" without tests | Require proper test coverage |
| Approve unfamiliar library usage | Verify with Context7/docs first |
| Nitpick formatting | Focus on substance, use linters for style |
| Accept over-engineering | Challenge unnecessary complexity |
| Skip database constraint verification | Always check schema matches code |

## Integration with Other Skills

**This skill requires using:**
- **Context7 MCP** - REQUIRED for verifying unfamiliar libraries/methods
- **systematic-debugging** - For complex data flow analysis
- **defense-in-depth** - For validation strategy

**Complementary skills:**
- **brainstorming** - When design seems questionable
- **writing-plans** - For suggesting refactoring approaches

## Example Review Process

```
1. Read PR description → Understand goal
2. View related models → Check constraints
3. Trace data flow → Identify edge cases
4. Check unfamiliar method with Context7
5. Review naming and readability
6. Verify validation exists at multiple layers
7. Check tests cover edge cases
8. Approve OR request specific changes
```

## The Bottom Line

**A good code review prevents bugs, ensures maintainability, and maintains quality standards.**

**Not rubber-stamping.** Not style nitpicking. Not over-engineering.

**Goal:** Clean, correct, maintainable code that handles edge cases and won't break in production.

If you can't confidently answer "will this work correctly in all scenarios?" → Request changes with specific rationale.
