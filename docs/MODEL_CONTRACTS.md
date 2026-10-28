# Model contracts (what each fine-tuned model must learn)

The code is the source of truth:
- the input and output types are in `backend/src/planner/llm/contracts.py`;
- the exact prompt layout is in `backend/src/planner/llm/prompts.py`.

`docs/contracts/<task>.json` holds the generated JSON Schemas and system prompt templates. Regenerate them with `uv run planner-export-contracts`.

## Prompt layout per training example

| Task | Messages | Assistant target |
|---|---|---|
| `planner.interview`, `planner.generate`, `planner.revise`, `coach.extract` | `system`: task instructions + style directive<br>`user`: the input object as JSON | one JSON object |
| `coach.checkin`, `coach.summarize` | `system`: instructions (+ style)<br>`user`: the input object as JSON | plain text |
| `coach.chat` | `system`: instructions + style + **context JSON**<br>then the real conversation turns (`user` / `assistant` …) | plain text reply |

Training data must be built with `planner.llm.prompts.build_messages(task, payload)`, so the format at training time matches the format at inference time exactly.

## Roles and adapters

Two LoRA adapters on one base model:
- **planner**: `planner.interview`, `planner.generate`, `planner.revise`
- **coach**: `coach.chat`, `coach.checkin`, `coach.extract`, `coach.summarize`

Within an adapter, the system prompt tells the tasks apart. Any task can also get its own adapter later by changing `model:` for that task in `config/models.yaml`.

## Per-task notes for the synthetic data

**planner.interview**
- Covers many domains: fitness/weight, running, studying/exams, languages, finance, skills, habits, and general goals.
- Must show adaptivity: follow-ups that depend on earlier answers (an age under 18 leads to a guardian question; a health condition leads to a doctor question; "never ran" means no question about distance).
- Never re-asks something already in `qa_history` or already stated in the goal description.
- Prefers `choice` with `options` where natural, and `number` with a `unit` for quantities.
- `finish` comes when the information is enough, or immediately when `questions_remaining == 0`. `profile` uses snake_case keys and numeric values.

**planner.generate**
- Dates fall inside today..deadline.
- Tasks due on the same day fit `minutes_per_day`, and the plan uses at most `days_per_week` active days.
- Task ids are stable (`t1`…), milestone ids `m1`…, metric keys are snake_case.
- Targets are safe (weight loss ≤ ~0.5–1 kg a week), and every `safety_flag` is respected.

**planner.revise**
- Operations are minimal, use ids that already exist, and include a `reason`.
- Includes many `should_revise: false` examples (weekly reviews with good adherence).
- Low adherence makes the plan *easier*, not harder.
- `explanation` is kind, user-facing, and in `style.language`.

**coach.chat**
- Kind but honest, and moves toward a concrete next step. At most one question per reply.
- Grounded in the context: it acknowledges `actions_taken` and never invents progress.
- Follows the style: language, length, tone, bullets or paragraphs, emojis.
- Safety: when flags are present, it is gentle and points to professional help.

**coach.checkin**
- One to three sentences, specific to the trigger and to the real task names or numbers. Ends with an easy question.

**coach.extract**
- Resolves relative dates ("yesterday", weekday names).
- Resolves a short "yes" against the previous assistant question.
- Uses only the given `task_id`s and `metric_key`s, and keeps event `text` short and in English.
- Includes many examples that produce no events.
- Must handle Hebrew, English and mixed messages.

**coach.summarize**
- About 150 words, English, third person. Keeps progress, struggles, constraints, preferences and emotional state, and drops small talk.
