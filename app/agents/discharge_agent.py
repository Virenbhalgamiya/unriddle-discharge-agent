from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.agents.auditor import AuditorAgent
from app.agents.draft_builder import build_draft_summary
from app.agents.planner import PlannerAgent
from app.llm.config_loader import get_path, load_config
from app.memory.correction_memory import CorrectionMemory
from app.models.agent_state import (
    MAX_STEPS,
    AgentResult,
    AgentState,
    AgentStatus,
    create_initial_state,
)
from app.models.evidence import EvidenceStore
from app.models.summary_models import (
    ClinicianReviewItem,
    ConflictReport,
    MedicationChange,
    MedicationReconciliationReport,
    PendingResultsReport,
    SafetyFlag,
    TraceStep,
)
from app.observability.trace_writer import append_trace_step, write_outputs, write_trace
from app.tools.escalation_tool import flag_for_clinician_review
from app.tools.medication_reconciliation import reconcile_medications
from app.tools.tool_registry import TASK_TO_TOOL, execute_tool

logger = logging.getLogger(__name__)


def _task_for_tool(tool_name: str) -> str | None:
    for task, tool in TASK_TO_TOOL.items():
        if tool == tool_name:
            return task
    return None


def _merge_state(state: AgentState, updates: dict[str, Any]) -> AgentState:
    new_state = dict(state)
    for key, value in updates.items():
        if key.startswith("_"):
            continue
        if key in ("safety_flags", "clinician_review_items", "evidence_store") and isinstance(value, list):
            new_state[key] = value
        else:
            new_state[key] = value
    return new_state  # type: ignore


class DischargeAgentRunner:
    def __init__(
        self,
        config_path: str | Path | None = None,
        llm_provider: str | None = None,
    ) -> None:
        self.config = load_config(config_path)
        self.llm_provider = llm_provider or self.config.get("llm_provider", "openai")
        self.memory = CorrectionMemory(get_path(self.config, "memory_db", "data/correction_memory.db"))
        self.planner = PlannerAgent()
        self.auditor = AuditorAgent()
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(AgentState)

        graph.add_node("planner", self._planner_node)
        graph.add_node("execute_tool", self._execute_tool_node)
        graph.add_node("auditor", self._auditor_node)
        graph.add_node("generate_draft", self._generate_draft_node)
        graph.add_node("handle_max_steps", self._handle_max_steps_node)

        graph.set_entry_point("planner")
        graph.add_edge("planner", "execute_tool")
        graph.add_edge("execute_tool", "auditor")
        graph.add_conditional_edges(
            "auditor",
            self._route_after_audit,
            {
                "planner": "planner",
                "generate_draft": "generate_draft",
                "handle_max_steps": "handle_max_steps",
            },
        )
        graph.add_edge("generate_draft", END)
        graph.add_edge("handle_max_steps", END)
        return graph.compile()

    def _planner_node(self, state: AgentState) -> AgentState:
        if state.get("current_step", 0) >= state.get("max_steps", MAX_STEPS):
            return _merge_state(state, {"status": AgentStatus.MAX_STEPS_REACHED.value})

        plan = self.planner.plan(state)
        step = TraceStep(
            step_number=state.get("current_step", 0) + 1,
            reasoning_summary=plan.get("reasoning_summary", ""),
            chosen_action=f"Plan next tool: {plan.get('next_tool')}",
            tool_name="planner",
            result="planned",
            next_decision=f"Execute {plan.get('next_tool')}",
        )
        return _merge_state(
            state,
            {
                "next_tool": plan.get("next_tool", ""),
                "reasoning_summary": plan.get("reasoning_summary", ""),
                "current_plan": plan.get("current_plan", []),
                "pending_tasks": plan.get("pending_tasks", []),
                "trace_log": append_trace_step(state, step),
                "status": AgentStatus.RUNNING.value,
            },
        )

    def _execute_tool_node(self, state: AgentState) -> AgentState:
        tool_name = state.get("next_tool", "")
        step_num = state.get("current_step", 0) + 1
        result = execute_tool(tool_name, state, self.memory)

        task = _task_for_tool(tool_name)
        completed = list(state.get("completed_tasks", []))
        pending = list(state.get("pending_tasks", []))
        if task and task not in completed and "error" not in result:
            completed.append(task)
            if task in pending:
                pending.remove(task)

        errors = [result["error"]] if result.get("error") else []
        step = TraceStep(
            step_number=step_num,
            reasoning_summary=state.get("reasoning_summary", ""),
            chosen_action=f"Execute tool: {tool_name}",
            tool_name=tool_name,
            tool_input={"patient_id": state.get("patient_id"), "task": task},
            tool_output={k: v for k, v in result.items() if not k.startswith("_")},
            result="error" if errors else "success",
            errors=errors,
            retries=result.get("retries", 0),
            next_decision="audit",
        )

        updates = {
            **{k: v for k, v in result.items() if not k.startswith("_")},
            "completed_tasks": completed,
            "pending_tasks": pending,
            "current_step": step_num,
            "trace_log": append_trace_step(state, step),
        }
        return _merge_state(state, updates)

    def _auditor_node(self, state: AgentState) -> AgentState:
        audit = self.auditor.audit(state)
        step = TraceStep(
            step_number=state.get("current_step", 0),
            reasoning_summary="Auditor validation",
            chosen_action="audit",
            tool_name="auditor",
            tool_output=audit,
            result="passed" if audit.get("audit_passed") and audit.get("all_tasks_complete") else "failed",
            next_decision="generate_draft" if audit.get("all_tasks_complete") and audit.get("audit_passed") else "replan",
        )
        status = state.get("status", AgentStatus.RUNNING.value)
        if not audit.get("audit_passed"):
            status = AgentStatus.AUDIT_FAILED.value
        elif audit.get("all_tasks_complete") and audit.get("audit_passed"):
            status = AgentStatus.COMPLETE.value

        return _merge_state(
            state,
            {
                "audit_failures": audit.get("audit_failures", []),
                "trace_log": append_trace_step(state, step),
                "status": status,
                "all_tasks_complete": audit.get("all_tasks_complete", False),
                "audit_passed": audit.get("audit_passed", False),
            },
        )

    def _route_after_audit(
        self, state: AgentState
    ) -> Literal["planner", "generate_draft", "handle_max_steps"]:
        if state.get("current_step", 0) >= state.get("max_steps", MAX_STEPS):
            return "handle_max_steps"
        if state.get("all_tasks_complete"):
            return "generate_draft"
        return "planner"

    def _generate_draft_node(self, state: AgentState) -> AgentState:
        reviews = list(state.get("clinician_review_items", []))
        for failure in state.get("audit_failures", []):
            review, flag, record = flag_for_clinician_review(
                reason="Audit failure",
                details=failure,
                section="audit",
                priority="high",
                memory=self.memory,
            )
            reviews.append(record)
        state_with_reviews = dict(state)
        state_with_reviews["clinician_review_items"] = reviews
        draft = build_draft_summary(state_with_reviews, self.memory, partial=False)
        synthesis_meta = state_with_reviews.get("_synthesis_metadata", {})
        step = TraceStep(
            step_number=state.get("current_step", 0) + 1,
            reasoning_summary=(
                f"Narrative synthesis complete. Quality score: {synthesis_meta.get('quality', {}).get('overall_score', 'n/a')}"
            ),
            chosen_action="synthesize_narrative",
            tool_name="narrative_agent",
            tool_output=synthesis_meta,
            result="success",
            next_decision="complete",
        )
        trace = append_trace_step(state_with_reviews, step)
        return _merge_state(
            state_with_reviews,
            {
                "draft_summary": draft.model_dump(mode="json"),
                "trace_log": trace,
                "status": AgentStatus.COMPLETE.value,
            },
        )

    def _handle_max_steps_node(self, state: AgentState) -> AgentState:
        review, flag, _ = flag_for_clinician_review(
            reason="Max steps reached",
            details=f"Agent reached max steps ({state.get('max_steps', MAX_STEPS)}). Partial draft generated.",
            section="workflow",
            priority="critical",
            memory=self.memory,
        )
        reviews = list(state.get("clinician_review_items", []))
        flags = list(state.get("safety_flags", []))
        reviews.append(review.model_dump(mode="json"))
        flags.append(flag.model_dump(mode="json"))

        partial_state = dict(state)
        partial_state["clinician_review_items"] = reviews
        partial_state["safety_flags"] = flags
        draft = build_draft_summary(partial_state, self.memory, partial=True)
        return _merge_state(
            state,
            {
                "clinician_review_items": reviews,
                "safety_flags": flags,
                "draft_summary": draft.model_dump(mode="json"),
                "status": AgentStatus.MAX_STEPS_REACHED.value,
            },
        )

    def run(
        self,
        patient_folder: str | Path,
        pdf_progress_callback: Any = None,
    ) -> AgentResult:
        folder = Path(patient_folder)
        patient_id = folder.name or "patient"
        max_steps = self.config.get("max_steps", MAX_STEPS)

        initial = create_initial_state(
            patient_id=patient_id,
            patient_folder=str(folder.resolve()),
            llm_provider=self.llm_provider,
            max_steps=max_steps,
            config=self.config,
            pdf_progress_callback=pdf_progress_callback,
        )

        final_state = self.graph.invoke(initial, config={"recursion_limit": 60})

        draft_data = final_state.get("draft_summary", {})
        if not draft_data:
            draft = build_draft_summary(final_state, self.memory)
            draft_data = draft.model_dump(mode="json")

        from app.models.summary_models import DischargeSummaryDraft

        draft = DischargeSummaryDraft(**draft_data)

        _, med_report, _, _ = reconcile_medications(
            final_state.get("evidence_store", []),
            final_state.get("loaded_documents", {}),
        )
        med_report.patient_id = patient_id

        traces_dir = get_path(self.config, "traces", "traces/")
        outputs_dir = get_path(self.config, "outputs", "outputs/")
        trace_paths = write_trace(patient_id, final_state.get("trace_log", []), traces_dir)

        out_dir = write_outputs(
            patient_id=patient_id,
            outputs_dir=outputs_dir,
            draft=draft_data,
            medication_report=med_report.model_dump(mode="json"),
            conflicts=final_state.get("conflicts", []),
            pending_results=final_state.get("pending_results", []),
            review_queue=final_state.get("clinician_review_items", []),
            safety_flags=final_state.get("safety_flags", []),
            evidence_store=final_state.get("evidence_store", []),
        )

        trace_steps = [TraceStep(**t) for t in final_state.get("trace_log", [])]
        evidence = EvidenceStore()
        for e in final_state.get("evidence_store", []):
            from app.models.evidence import EvidenceItem
            evidence.add(EvidenceItem(**e))

        return AgentResult(
            patient_id=patient_id,
            status=final_state.get("status", AgentStatus.COMPLETE.value),
            draft_summary=draft,
            safety_flags=[SafetyFlag(**f) for f in final_state.get("safety_flags", [])],
            clinician_review_items=[ClinicianReviewItem(**r) for r in final_state.get("clinician_review_items", [])],
            medication_changes=[MedicationChange(**c) for c in final_state.get("medication_changes", [])],
            conflicts=[
                ConflictReport(
                    field_name=c.get("field_name", ""),
                    values=c.get("values", []),
                    message=c.get("message", ""),
                )
                for c in final_state.get("conflicts", [])
            ],
            pending_results=[
                PendingResultsReport(
                    description=p.get("description", ""),
                    source_document=p.get("source_document", ""),
                    page_number=int(p.get("page_number", 0)),
                )
                for p in final_state.get("pending_results", [])
            ],
            evidence_store=evidence,
            trace_log=trace_steps,
            output_dir=str(out_dir),
            trace_paths=trace_paths,
        )


def run_discharge_agent(
    patient_folder: str | Path,
    config_path: str | Path | None = None,
    llm_provider: str | None = None,
    pdf_progress_callback: Any = None,
) -> AgentResult:
    runner = DischargeAgentRunner(config_path=config_path, llm_provider=llm_provider)
    return runner.run(patient_folder, pdf_progress_callback=pdf_progress_callback)
