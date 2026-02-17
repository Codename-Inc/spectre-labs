# Todo CLI App

## Phase 1: Data Layer

- [ ] 1.1 Create `lib/models.py` with a `Todo` dataclass (title, done, id)
  - [ ] Define dataclass with auto-incrementing id
  - [ ] Add `__str__` method for display
- [ ] 1.2 Create `lib/store.py` with `add_todo()`, `list_todos()`, `complete_todo()`
  - [ ] In-memory list storage
  - [ ] Return newly created todo from add
  - [ ] Raise ValueError for invalid todo id in complete

## Phase 2: CLI Layer

- [ ] 2.1 Create `cli.py` that imports from store and provides add/list/done commands
  - [ ] Use argparse with subcommands
  - [ ] Pretty-print todo list with checkboxes
- [ ] 2.2 Add basic input validation
  - [ ] Reject empty todo titles
  - [ ] Handle non-existent todo ids gracefully
