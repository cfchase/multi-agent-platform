# Autonomous Agent Workflow

This document defines a workflow for running Claude agents autonomously for extended periods with incremental verification. Use this workflow for complex, multi-step tasks that benefit from continuous progress tracking and agent-based verification.

## When to Use This Workflow

**Use Autonomous Workflow when:**
- Task requires 5+ implementation steps
- Multiple agents can provide verification value
- You want to run without frequent interruptions
- Progress observability is important

**Use Incremental Development Workflow instead when:**
- Task is smaller (< 5 steps)
- User wants frequent checkpoints and approval
- Task is exploratory or requirements are unclear

## Directory Structure

Create a progress directory at `.tmp/{feature-name}/`:

```
.tmp/{feature-name}/
├── plan.md              # Implementation plan
├── progress.md          # Running progress log (append-only)
├── current-step.md      # Current step details and status
├── verification/        # Agent verification reports
│   ├── code-review-{n}.md
│   ├── test-results-{n}.md
│   └── issues-{n}.md
├── artifacts/           # Supporting files
│   ├── screenshots/
│   └── logs/
└── summary.md           # Final summary (on completion)
```

## Progress Reporting

### progress.md Format

```markdown
# Progress Report: {Feature Name}

## Status: {IN_PROGRESS | BLOCKED | COMPLETED | ESCALATED}
## Last Updated: {timestamp}

---

### Entry {n}: {timestamp}
**Step**: {step number/name}
**Action**: {what was done}
**Result**: {SUCCESS | FAILED | PARTIAL}
**Details**:
```
{code snippets, test output, or relevant information}
```
**Next**: {what happens next}

---
```

### current-step.md Format

```markdown
# Current Step: {Step Name}

## Status: {PENDING | IN_PROGRESS | VERIFYING | BLOCKED | COMPLETED}
## Started: {timestamp}
## Attempts: {n}/3

## Objective
{What this step accomplishes}

## Files Being Modified
| File | Status | Notes |
|------|--------|-------|
| path/to/file.ts | MODIFIED | {brief note} |

## Verification Status
- [ ] Linting passes
- [ ] Type checking passes
- [ ] Unit tests pass
- [ ] Code review agent approved

## Issues Found
1. {Issue description}
   - **Fix Attempt 1**: {what was tried}
   - **Result**: {outcome}
```

## Verification Checkpoints

Spawn verification agents at these points:

| Checkpoint | Agent | Trigger |
|------------|-------|---------|
| After implementing component + tests | code-review-expert | Review code quality |
| After writing test files | quality-test-engineer | Validate test coverage |
| After UI changes | quality-test-engineer | Run E2E tests |
| After major milestone | code-review-expert | Architectural review |

### Spawning Verification Agents

Use the Task tool to spawn verification agents:

```
Task: code-review-expert
Prompt: |
  Review the changes made in step {n} of the autonomous workflow.

  Context:
  - Feature: {feature-name}
  - Files changed: {list}
  - Plan: .tmp/{feature}/plan.md
  - Current step: .tmp/{feature}/current-step.md

  Write your review to: .tmp/{feature}/verification/code-review-{n}.md

  Return APPROVED, NEEDS_CHANGES, or BLOCKED with detailed reasoning.
```

## Error Handling

### Retry Logic

When verification fails:

1. **Attempt 1**: Analyze failure, apply fix
2. **Attempt 2**: Different approach if first fix didn't work
3. **Attempt 3**: Minimal fix or workaround
4. **After 3 attempts**: Escalate to user

```
attempt = 0
max_attempts = 3

while attempt < max_attempts:
    result = run_verification()
    if result.passed:
        log_success()
        proceed_to_next_step()
        break
    else:
        attempt += 1
        log_attempt(attempt, result.issues)
        if attempt < max_attempts:
            apply_fixes(result.issues)
        else:
            escalate_to_user()
            STOP
```

### Escalation

When escalating to user:
1. Update `progress.md` with ESCALATED status
2. Write detailed `verification/issues-{n}.md` with:
   - What was attempted
   - Why it failed
   - Recommended next steps
3. Stop and await user input

## Running Tests

```bash
# Quick verification (after each file change)
make lint
cd frontend && npx tsc --noEmit

# Standard verification (after each logical step)
make test

# Full E2E verification (after UI changes)
make test-e2e
```

## Agent Responsibilities

| Agent | When to Use | Responsibilities |
|-------|-------------|------------------|
| chief-architect-orchestrator | Multi-component work | Plan, coordinate, architectural decisions |
| software-architect-engineer | Single-component work | Implement code, write tests, fix issues |
| code-review-expert | After implementation | Review code quality, check conventions |
| quality-test-engineer | After writing tests | Run tests, validate coverage |
| root-cause-debugger | When tests fail repeatedly | Investigate root cause, provide fixes |

## Workflow Phases

### Phase 1: Setup
1. Create `.tmp/{feature}/` directory structure
2. Write initial `plan.md` or copy from approved plan
3. Initialize `progress.md` with IN_PROGRESS status

### Phase 2: Implementation
For each step:
1. Update `current-step.md` with step details
2. Implement changes
3. Run quick verification (lint, typecheck)
4. Update `progress.md` with entry
5. If verification checkpoint reached, spawn verification agent

### Phase 3: Verification
1. Review agent reports
2. Apply fixes if needed (up to 3 attempts)
3. Escalate if blocked

### Phase 4: Completion
1. Run full test suite
2. Write `summary.md` with:
   - What was accomplished
   - Files changed
   - Test coverage
   - Lessons learned
3. Update `progress.md` with COMPLETED status

## Best Practices

1. **Write progress frequently**: Update progress.md after every significant action
2. **Keep current-step.md accurate**: Always reflect what you're working on
3. **Use verification agents**: Don't skip checkpoints
4. **Fail fast**: If something isn't working after 3 attempts, escalate
5. **Document decisions**: Record why you made certain choices
6. **Clean up**: Kill dangling processes after tests

## Example Workflow Execution

```
1. mkdir -p .tmp/my-feature/verification
2. Copy plan to .tmp/my-feature/plan.md
3. Initialize progress.md: Status: IN_PROGRESS
4. For step 1:
   - Write current-step.md
   - Implement changes
   - Run lint/typecheck
   - Write progress entry
5. Spawn code-review-expert
6. Review report, apply fixes if needed
7. Continue to step 2...
...
N. Write summary.md
N+1. Update progress.md: Status: COMPLETED
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Test processes don't terminate | Run `pkill -f vitest; pkill -f "node.*test"` |
| Agent verification fails repeatedly | Check verification/issues-{n}.md for patterns |
| Database state inconsistent | Use unique test data IDs; run cleanup |
| E2E tests flaky | Add proper waits; use route mocking |

## See Also

- [INCREMENTAL-WORKFLOW.md](INCREMENTAL-WORKFLOW.md) - Step-by-step with manual review
- [TESTING.md](TESTING.md) - Testing strategies
- [../CLAUDE.md](../CLAUDE.md) - Project guidelines
