# Incremental Development Workflow

This document defines how Claude should work on complex features with human-in-the-loop review at each step. Use this workflow when the user wants visibility and approval at each stage.

## When to Use This Workflow

**Use Incremental Workflow when:**
- Features with 5+ file changes across multiple modules
- Database schema + API + frontend changes
- Architectural changes
- User wants frequent checkpoints and approval
- Task is exploratory or requirements are unclear

**Don't Use For:**
- Simple bug fixes (single file, < 50 lines)
- Documentation-only changes
- Configuration updates
- Trivial refactoring

**Use Autonomous Workflow instead when:**
- User wants you to run without interruptions
- Task requires 5+ steps and verification agents can provide value

## Workflow Overview

```
1. Create Feature Branch
2. Write Implementation Plan
3. For Each Step:
   - Mark as In Progress
   - Implement changes
   - Write tests
   - Run tests
   - Commit
   - Mark as Awaiting Review
   - STOP - Wait for user approval
4. After all steps approved, merge to main
```

## Step 0: Create Feature Branch

**CRITICAL**: Always create a feature branch before starting complex work.

```bash
# Choose appropriate prefix
git checkout -b feature/<feature-name>    # New features
git checkout -b refactor/<feature-name>   # Refactoring
git checkout -b fix/<issue-description>   # Bug fixes
```

**Important**:
- All work on feature branch, NOT on main
- Merge to main only after all steps complete and final review
- This prevents contaminating main with incomplete work

## Step 1: Create Implementation Plan

Write a detailed plan to `.tmp/<feature>-implementation-plan.md`:

```markdown
# Feature Implementation Plan: [Feature Name]

## Overview
Brief description of the feature and why it's needed.

## Step 1: [Step Name]
Status: ⏳ Pending
Files: list of files to change
Testing: make test-backend / make test-frontend / make test
Success Criteria: What defines completion of this step
Commit: feat: brief description

## Step 2: [Step Name]
Status: ⏳ Pending
...

## Step N: [Final Step]
...
```

**Planning Guidelines:**
- Break feature into 5-10 logical steps
- Each step should be independently testable and committable
- Include success criteria for each step
- Plan testing strategy for each step

## Step 2: Track Progress

Use status markers in the plan file:

| Marker | Status | Meaning |
|--------|--------|---------|
| ⏳ | **Pending** | Not started |
| 🚧 | **In Progress** | Currently working on this step |
| ✅ | **Complete** | Implementation finished |
| ⏸️ | **Awaiting Review** | Waiting for user approval |
| 🎉 | **Approved** | Reviewed and approved, proceed |

**Update the plan file after each step** to maintain clear progress tracking.

## Step 3: Per-Step Workflow

For each step in your plan:

```bash
# 1. Update plan file - mark step as 🚧 In Progress

# 2. Implement changes for THAT STEP ONLY
#    - Focus on single logical unit of work
#    - Don't mix multiple steps in one commit

# 3. Write tests for new code (MANDATORY)
#    - Backend: Create test file in tests/
#    - Frontend: Create .test.tsx file
#    - Aim for >80% coverage of new code

# 4. Run step-specific tests
make test-backend              # For backend changes
make test-frontend             # For frontend changes
make test                      # For full-stack changes

# 5. Fix any test failures
#    - All tests must pass before committing

# 6. Create focused git commit
git add <files-for-this-step> <test-files>
git commit -m "type: brief description"

# 7. Update plan file - mark step as ✅ Complete

# 8. Update plan file - mark step as ⏸️ Awaiting Review

# 9. STOP - Wait for user review and approval

# 10. After approval:
#     - Update plan: ⏸️ → 🎉 Approved
#     - Next step: ⏳ → 🚧 In Progress
```

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

**Format:**
```
<type>: <brief description>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring (no functional changes)
- `test:` - Adding or updating tests
- `docs:` - Documentation only
- `chore:` - Build process, dependencies

**Guidelines:**
- Keep focused on single step (no multi-step commits)
- Write in imperative mood ("add" not "added")
- Keep under 72 characters
- Don't include AI assistant attribution

## Testing Strategy

**CRITICAL**: Write tests as part of EVERY step (not at the end).

### Step-Level Testing
```bash
# Run only tests related to current changes
pytest tests/api/test_items.py -v
npm test -- ItemBrowser.test.tsx
```

### Test Coverage
- Aim for >80% coverage of new code
- Cover happy path, error cases, edge cases
- Don't test framework internals

### Integration Testing
After all steps complete:
```bash
make test                    # All tests
make test-e2e                # E2E tests
```

**Test Requirements:**
- All tests must pass before moving to next step
- Tests are committed WITH implementation code
- No skipping tests

## Review Checkpoints

**Why Review Checkpoints?**
- Catch issues early (easier to fix)
- Provides natural breakpoints for context switching
- Maintains clean, reviewable git history
- Allows course correction before too much work is done

**When to Request Review:**
- After each step (for complex features)
- After groups of related steps (for moderate features)
- Before major architectural changes
- When uncertain about implementation approach

## Example Plan

```markdown
# Feature Implementation Plan: Item Categories

## Overview
Add category support to items - users can organize items into categories.

## Step 1: Database Model
Status: ⏳ Pending
Files: backend/app/models/, backend/alembic/versions/
Testing: make test-backend
Success Criteria:
- Category model exists with name, description
- Item has category_id foreign key
- Migration created and tested
Commit: feat: add Category model and Item relationship

## Step 2: API Endpoints
Status: ⏳ Pending
Files: backend/app/api/routes/v1/categories/
Testing: make test-backend
Success Criteria:
- CRUD endpoints for categories
- Items filterable by category
- Tests cover success and error cases
Commit: feat: add category CRUD endpoints

## Step 3: Frontend Service
Status: ⏳ Pending
Files: frontend/src/services/categoryService.ts
Testing: make test-frontend
Success Criteria:
- categoryService with all API methods
- TypeScript types defined
Commit: feat: add category service layer

## Step 4: Category Browser UI
Status: ⏳ Pending
Files: frontend/src/app/Categories/
Testing: make test-frontend
Success Criteria:
- CategoryBrowser component
- List, create, edit, delete categories
Commit: feat: add CategoryBrowser component

## Step 5: Item-Category Integration
Status: ⏳ Pending
Files: frontend/src/app/Items/
Testing: make test-frontend, make test-e2e
Success Criteria:
- Category selector in item forms
- Category filter in item list
Commit: feat: integrate categories with items UI
```

## Advanced Techniques

### Parallel Development
For independent steps, work on multiple branches:
```bash
# Branch for Step 1 (database)
git checkout -b feature/categories-model

# Branch for Step 3 (frontend service) - if independent
git checkout main
git checkout -b feature/categories-service
```

Merge in sequence once both are reviewed.

### Checkpoint Commits
Within a single step, use checkpoint commits:
```bash
# WIP commit (don't push)
git commit -m "WIP: partial implementation of category model"

# Later, squash WIP commits before review
git rebase -i HEAD~3
```

### Feature Flags
For very large features, use feature flags to merge to main before complete:
```python
if settings.ENABLE_CATEGORIES:
    # New code path
else:
    # Old code path (fallback)
```

Allows incremental merging while keeping main stable.

## Common Pitfalls

### Skipping the Plan
Writing code without a plan leads to:
- Forgetting important steps
- Missing edge cases
- Poor organization

**Solution**: Always write the plan first, even if it takes 30 minutes.

### Too-Large Steps
Making steps too large defeats the purpose:
- Hard to review
- Risky to commit
- Difficult to rollback

**Solution**: If a step touches >10 files or takes >4 hours, break it down.

### Skipping Tests
Writing tests "later" never works:
- Forget what needs testing
- Hard to achieve coverage
- Regressions slip through

**Solution**: Write tests AS PART OF each step, commit together.

### Mixing Steps
Implementing multiple steps in one commit:
- Unclear what changed
- Hard to review
- Can't rollback individually

**Solution**: Discipline yourself to one step at a time. Update plan file.

### Ignoring Reviews
Proceeding without approval on awaiting-review steps:
- Might build on wrong foundation
- Miss early feedback
- Waste time on wrong approach

**Solution**: Actually wait for review. Use time to work on other tasks.
