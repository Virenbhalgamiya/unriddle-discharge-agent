from __future__ import annotations

from typing import Any

from app.llm.base_provider import LLMMessage
from app.llm.provider_factory import get_provider
from app.tools.tool_registry import TASK_TO_TOOL


class PlannerAgent:
    """Plans next tool execution. Never writes clinical summary content."""

    TASK_ORDER = [
        "load_documents",
        "extract_fields",
        "medication_reconciliation",
        "detect_missing_fields",
        "detect_conflicts",
        "detect_pending_results",
        "check_interactions",
        "finalize_review_queue",
    ]

    def plan(self, state: dict[str, Any]) -> dict[str, Any]:
        pending = list(state.get("pending_tasks", []))
        completed = set(state.get("completed_tasks", []))
        reasoning = ""

        next_task = None
        for task in self.TASK_ORDER:
            if task not in completed and task in pending:
                next_task = task
                break

        if next_task is None:
            for task in self.TASK_ORDER:
                if task not in completed:
                    next_task = task
                    break

        if next_task is None:
            return {
                "next_tool": "finalize_review_queue",
                "reasoning_summary": "All tasks complete; finalizing review queue.",
                "current_plan": self.TASK_ORDER,
                "pending_tasks": [],
            }

        next_tool = TASK_TO_TOOL.get(next_task, next_task)
        reasoning = f"Next required task: {next_task}. Executing tool {next_tool}."

        if state.get("audit_failures"):
            reasoning = f"Re-planning after audit failures: {state['audit_failures'][:2]}. {reasoning}"

        provider_name = state.get("llm_provider", "mock")
        if state.get("audit_failures"):
            try:
                provider = get_provider(provider_name)
                llm_result = provider.structured_complete(
                    messages=[
                        LLMMessage(role="system", content="You are a clinical agent planner. Choose the next tool only."),
                        LLMMessage(
                            role="user",
                            content=(
                                f"Pending tasks: {pending}. Completed: {list(completed)}. "
                                f"Suggested next tool: {next_tool}. Audit failures: {state.get('audit_failures', [])}. "
                                "Return next_tool and reasoning_summary."
                            ),
                        ),
                    ],
                    schema={
                        "type": "object",
                        "properties": {
                            "next_tool": {"type": "string"},
                            "reasoning_summary": {"type": "string"},
                        },
                        "required": ["next_tool", "reasoning_summary"],
                    },
                )
                reasoning = llm_result.get("reasoning_summary", reasoning)
            except Exception:
                pass

        remaining = [t for t in self.TASK_ORDER if t not in completed and t != next_task]
        if next_task not in completed:
            remaining.insert(0, next_task) if next_task in remaining else None

        return {
            "next_tool": next_tool,
            "reasoning_summary": reasoning,
            "current_plan": self.TASK_ORDER,
            "pending_tasks": [t for t in self.TASK_ORDER if t not in completed],
        }
