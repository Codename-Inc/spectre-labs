# Scope Clarifications — Token-Efficient Build Loop (Phase Owner Pattern)

**Concept**: Replace per-task full-context reads with phase owners that dispatch parallel subagents with surgical context
**Confirmed boundaries**: Build stage phase owners, code review isolation, validate subagent optimization

---

## Question 1: Subagent Commit Strategy

Currently each build iteration commits independently (Step 5 in build.md). With parallel subagents per wave, how should commits work?

**Option A**: Each subagent commits its own work independently (current behavior, just parallelized)
**Option B**: Phase owner coordinates — subagents make changes but don't commit, phase owner commits after wave completes
**Option C**: Each subagent commits, phase owner does a squash/merge commit at phase boundary

<response>Option A — each commit independently. Parallelization planning should ensure there are no conflicts.</response>

---

## Question 2: Subagent Token Tracking

Currently `BuildStats` tracks tokens per iteration via `result` events. With subagents dispatched via the Task tool, their token usage is invisible to the outer stream parser.

Should we:
**Option A**: Accept that subagent tokens won't be tracked in the dashboard (simpler, ship faster)
**Option B**: Have subagents report token usage back to the phase owner, who aggregates it
**Option C**: Find a way to capture subagent tokens at the stream level (may require infrastructure work)

<response>Need to get it from the JSONL or transcripts. Broadly — need to get better at token tracking, current tracking may not be accurate.</response>

---

## Question 3: Build Progress Doc Ownership

Currently the build agent writes to the progress file after each task. With parallel subagents in a wave, multiple agents could write to the same progress doc simultaneously.

Should the phase owner be the **sole writer** of the progress doc (aggregating results from subagents), or should subagents each append their own iteration log?

<response>Subagents can append/edit. Conflicts should be minimal.</response>

---

## Question 4: Phase Owner Prompt — New or Modified?

The current `build.md` prompt assumes one agent per task reading all docs. We need a phase owner variant.

**Option A**: Create a new `build_phase_owner.md` prompt alongside existing `build.md` (clean separation, legacy preserved)
**Option B**: Modify `build.md` with conditional sections for phase owner vs single-task mode
**Option C**: Replace `build.md` entirely — phase owner pattern becomes the only build mode

<response>Open to options — to be decided during planning.</response>

---

## Question 5: Subagent Prompt Template

Subagents receive context from the phase owner via the Task tool prompt. Do we need a formal prompt template for subagents (like `build_subagent.md`), or is the Task tool prompt sufficient since the phase owner constructs it dynamically?

<response>Dynamic with some instructions. The existing spectre:execute workflow does this well and should be used as a model (from /Dev/spectre).</response>
