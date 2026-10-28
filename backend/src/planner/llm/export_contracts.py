"""Write the JSON Schema of every task's input and output to docs/contracts/ (``uv run planner-export-contracts``)."""

import json
import sys
from pathlib import Path

from planner.config import BACKEND_DIR
from planner.llm.contracts import TASKS
from planner.llm.prompts import SYSTEM_PROMPTS, CHECKIN_SYSTEM, COACH_CHAT_SYSTEM


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND_DIR.parent / "docs" / "contracts"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts = {**SYSTEM_PROMPTS, "coach.chat": COACH_CHAT_SYSTEM, "coach.checkin": CHECKIN_SYSTEM}
    for task, spec in TASKS.items():
        doc = {
            "task": task,
            "output_kind": "json" if spec.output else "text",
            "input_schema": spec.input.model_json_schema(),
            "output_schema": spec.output.model_json_schema() if spec.output else {"type": "string"},
            "system_prompt_template": prompts[task],
        }
        (out_dir / f"{task}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(TASKS)} contracts to {out_dir}")


if __name__ == "__main__":
    main()
