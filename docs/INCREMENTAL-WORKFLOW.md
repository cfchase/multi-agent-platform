# Incremental Development Workflow

For complex features with multiple steps (e.g., new database models with API routes and frontend), use this incremental approach to manage development systematically.

## When to Use This Workflow

### Use For:
- Features with 5+ file changes across multiple modules
- Database schema changes + API changes + frontend changes
- Architectural changes
- Features requiring multiple days of development
- Any feature that benefits from step-by-step planning and review

### Don't Use For:
- Simple bug fixes (single file, < 50 lines)
- Documentation-only changes
- Configuration updates
- Trivial refactoring

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
   - Wait for approval
4. Merge to main
```

## Step 0: Create Feature Branch

**CRITICAL**: Always create a feature branch before starting complex work.

```bash
# Choose appropriate prefix
git checkout -b feature/<feature-name>    # New features
git checkout -b refactor/<feature-name>   # Refactoring
git checkout -b fix/<issue-description>   # Bug fixes

# Example
git checkout -b feature/user-authentication
```

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
| ⏸️ | **Awaiting Review** | Waiting for manual approval |
| 🎉 | **Approved** | Reviewed and approved |

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

# 9. STOP - Wait for manual review and approval

# 10. After approval, proceed to next step
```

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

**Format:**
```
<type>: <brief description>

[optional body with more detail]
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring (no functional changes)
- `test:` - Adding or updating tests
- `docs:` - Documentation only
- `chore:` - Build process, dependencies

**Examples:**
```bash
git commit -m "feat: add user authentication endpoints"
git commit -m "refactor: extract item service layer"
git commit -m "test: add comprehensive item API tests"
git commit -m "docs: add authentication documentation"
```

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
- Catch issues early
- Provides natural breakpoints
- Maintains clean git history
- Allows course correction

**When to Request Review:**
- After each step (for complex features)
- After groups of related steps
- Before major architectural changes
- When uncertain about approach

## Example Plan

```markdown
# Feature Implementation Plan: Item Categories

## Overview
Add category support to items - users can organize items into categories.

## Step 1: Database Model
Status: ⏳ Pending
Files: backend/app/models.py, backend/alembic/versions/
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
- Tests cover user interactions
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

## Common Pitfalls

### Skipping the Plan
Writing code without a plan leads to:
- Forgetting important steps
- Missing edge cases
- Poor organization

**Solution**: Always write the plan first.

### Too-Large Steps
Making steps too large defeats the purpose:
- Hard to review
- Risky to commit
- Difficult to rollback

**Solution**: If a step touches >10 files, break it down.

### Skipping Tests
Writing tests "later" never works:
- Forget what needs testing
- Hard to achieve coverage
- Regressions slip through

**Solution**: Write tests AS PART OF each step.

### Mixing Steps
Implementing multiple steps in one commit:
- Unclear what changed
- Hard to review
- Can't rollback individually

**Solution**: One step at a time, update plan file.

## See Also

- [AUTONOMOUS-WORKFLOW.md](AUTONOMOUS-WORKFLOW.md) - For extended autonomous work
- [TESTING.md](TESTING.md) - Testing strategies
- [../CLAUDE.md](../CLAUDE.md) - Project guidelines
