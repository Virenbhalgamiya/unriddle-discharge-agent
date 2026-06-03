from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.discharge_agent import run_discharge_agent
from app.evaluation.metrics import compute_reward
from app.evaluation.simulated_doctor import SimulatedDoctor
from app.llm.config_loader import get_path, load_config
from app.memory.correction_memory import CorrectionMemory
from app.models.summary_models import DischargeSummaryDraft


class EvaluationRunner:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config = load_config(config_path)
        self.memory = CorrectionMemory(get_path(self.config, "memory_db", "data/correction_memory.db"))
        self.doctor = SimulatedDoctor()
        self.fixtures_root = Path(__file__).resolve().parents[2] / "fixtures" / "patient_folders"
        self.output_dir = get_path(self.config, "outputs", "outputs/") / "evaluation"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_folders(self, split: str) -> list[str]:
        eval_cfg = self.config.get("evaluation", {})
        key = f"{split}_folders"
        return eval_cfg.get(key, [])

    def _evaluate_folder(
        self,
        folder_name: str,
        llm_provider: str | None = None,
    ) -> dict[str, Any]:
        folder = self.fixtures_root / folder_name
        if not folder.exists() or not list(folder.glob("*.pdf")):
            return {}
        agent_result = run_discharge_agent(folder, llm_provider=llm_provider or "mock")
        draft = agent_result.draft_summary
        _, edited = self.doctor.generate_pair(draft)
        ctx = {
            "conflicts": [c.model_dump() for c in agent_result.conflicts],
            "missing_fields": agent_result.draft_summary.sections,
            "pending_results": [p.model_dump() for p in agent_result.pending_results],
            "safety_flags": [f.model_dump() for f in agent_result.safety_flags],
        }
        metrics = compute_reward(draft, edited, ctx)
        return {
            "folder": folder_name,
            "metrics": metrics,
            "status": agent_result.status,
            "draft": draft,
            "edited": edited,
        }

    def run_split(self, split: str, llm_provider: str | None = None) -> list[dict[str, Any]]:
        results = []
        for folder_name in self._resolve_folders(split):
            evaluated = self._evaluate_folder(folder_name, llm_provider)
            if not evaluated:
                continue
            results.append(
                {
                    "folder": folder_name,
                    "split": split,
                    "metrics": evaluated["metrics"],
                    "status": evaluated["status"],
                }
            )
        return results

    def _learn_from_edits(self, draft: DischargeSummaryDraft, edited: DischargeSummaryDraft) -> None:
        orig_map = {s.name: s.content for s in draft.sections}
        edit_map = {s.name: s.content for s in edited.sections}
        for section, orig_content in orig_map.items():
            edit_content = edit_map.get(section, "")
            if orig_content != edit_content:
                self.memory.record_correction(
                    mistake=orig_content[:200],
                    correction=edit_content[:200],
                    affected_section=section,
                    recommendation=f"Apply formatting improvement for {section}",
                )

    def run_full_evaluation(self, llm_provider: str | None = None) -> dict[str, Any]:
        provider = llm_provider or "mock"
        train_folders = self._resolve_folders("train")

        self.memory.clear()
        cold_results: list[dict[str, Any]] = []
        for folder_name in train_folders:
            evaluated = self._evaluate_folder(folder_name, provider)
            if evaluated:
                cold_results.append(evaluated)

        before_avg = self._average_reward(cold_results)
        learning_curve: list[dict[str, Any]] = []

        for step, folder_name in enumerate(train_folders, start=1):
            evaluated = self._evaluate_folder(folder_name, provider)
            if not evaluated:
                continue
            self._learn_from_edits(evaluated["draft"], evaluated["edited"])
            warm = self._evaluate_folder(folder_name, provider)
            if warm:
                learning_curve.append(
                    {
                        "step": step,
                        "folder": folder_name,
                        "reward": warm["metrics"]["composite_reward"],
                        "edit_score": warm["metrics"]["edit_score"],
                    }
                )

        after_avg = (
            sum(p["reward"] for p in learning_curve) / len(learning_curve) if learning_curve else before_avg
        )

        all_results: dict[str, list] = {}
        for split in ("train", "val", "test"):
            all_results[split] = self.run_split(split, provider)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "cold_baseline_then_incremental_correction_memory",
            "splits": all_results,
            "before_avg_reward": before_avg,
            "after_avg_reward": after_avg,
            "improvement_delta": after_avg - before_avg,
            "learning_curve": learning_curve,
        }
        report_path = self.output_dir / "evaluation_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        learning_path = self.output_dir / "learning_report.json"
        learning_path.write_text(
            json.dumps(
                {
                    "part": 2,
                    "description": "Learning from simulated doctor edits via correction memory",
                    "before_after": {"before": before_avg, "after": after_avg, "delta": after_avg - before_avg},
                    "learning_curve": learning_curve,
                    "limitations": [
                        "Simulated doctor policy is rule-based, not a real clinician",
                        "Memory affects formatting only; safety literals unchanged",
                        "Small train split; cold-start remains a risk",
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return report

    @staticmethod
    def _average_reward(results: list[dict[str, Any]]) -> float:
        if not results:
            return 0.0
        return sum(r["metrics"]["composite_reward"] for r in results) / len(results)
