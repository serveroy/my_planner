# my_planner
An app developed for the LLM course at Bar-Ilan University, aimed at creating personalized plans.

You describe a goal, where you are today, a deadline, how much time you have and how you want to be answered. A **Planner** model interviews you with adaptive questions and builds a structured plan. A **Coach** model then chats with you, checks in on its own ("did you work out today?"), logs your progress from the conversation, and the plan adapts. You choose whether updates are applied automatically or need your approval. Everything works in **Hebrew and English**, including right-to-left layout.

Each model will be a fine-tuned open-source LLM. Until those exist, built-in mock models stand in, so the whole app runs end to end today.

```
backend/    FastAPI + SQLite: accounts, goals, intake, plans, revisions, chat, check-in scheduler
frontend/   Expo (React Native) app for iOS, Android and web
docs/       ARCHITECTURE.md, MODEL_CONTRACTS.md, contracts/*.json (I/O schema per model task)
```

## Run it

Backend (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
cd backend && uv sync && uv run uvicorn planner.main:app --port 8000
```

App:

```bash
cd frontend && npm install && npx expo start
```

Press `w` for web, `i` for the iOS simulator, `a` for the Android emulator. On a physical phone, set `EXPO_PUBLIC_API_URL=http://<your-computer-LAN-IP>:8000` before `npx expo start`.

Tests:

```bash
cd backend && uv run pytest
```

**Demo tip:** check-ins normally fire on a timer, in the user's timezone. In the app, go to **Settings → Developer tools** and press *Simulate 20:30 tonight* or *Simulate 09:00 tomorrow* to trigger them on demand.

## The models

| Task | Role | What it does |
|---|---|---|
| `planner.interview` | Planner | Picks the next intake question, or finishes with a normalized profile |
| `planner.generate` | Planner | Builds a structured plan: milestones, scheduled tasks, metrics |
| `planner.revise` | Planner | Proposes minimal edit operations to the plan |
| `coach.chat` | Coach | Writes a kind, grounded reply |
| `coach.checkin` | Coach | Writes a proactive check-in message |
| `coach.extract` | Coach | Pulls events from a message: task done, weight logged, new constraint, change request, mood |
| `coach.summarize` | Coach | Keeps rolling conversation memory |

`backend/config/models.yaml` decides what serves each task. To switch from the mocks to fine-tuned models, serve one base model with two LoRA adapters through any OpenAI-compatible server and set `backend: openai`:

```bash
vllm serve <base-model> --port 8001 --enable-lora --lora-modules planner=./adapters/planner coach=./adapters/coach
```

Model inputs and outputs are Pydantic contracts in `backend/src/planner/llm/contracts.py`, and the prompts are in `llm/prompts.py`. Together they define the format of the synthetic fine-tuning data; see [docs/MODEL_CONTRACTS.md](docs/MODEL_CONTRACTS.md). Every model call is also logged in chat format to `backend/data/llm_logs/<task>.jsonl`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the flows: intake → plan, chat, revisions, check-ins, and safety.
