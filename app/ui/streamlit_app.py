"""Streamlit UI for Clinical Discharge Summary Agent."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.agents.discharge_agent import run_discharge_agent
from app.evaluation.summary_rubric import evaluate_summary_quality
from app.llm.config_loader import load_config
from app.llm.provider_factory import PROVIDERS
from app.memory.correction_memory import CorrectionMemory
from app.models.constants import DRAFT_BANNER
from app.tools.pdf_reader import tesseract_available
from app.ui.upload_utils import stage_uploaded_pdfs

st.set_page_config(
    page_title="Discharge Summary Agent",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0d9488 100%);
        color: white; padding: 1.5rem 1.75rem; border-radius: 12px; margin-bottom: 1.25rem;
    }
    .hero h1 { color: white; margin: 0; font-size: 1.75rem; }
    .hero p { margin: 0.5rem 0 0; opacity: 0.92; }
    .draft-banner {
        background: #fef3c7; color: #92400e; border: 1px solid #fcd34d;
        padding: 0.75rem 1rem; border-radius: 8px; font-weight: 600; margin-bottom: 1rem;
    }
    .quality-pill {
        display: inline-block; padding: 0.35rem 0.75rem; border-radius: 999px;
        font-weight: 700; font-size: 0.9rem;
    }
    .quality-high { background: #d1fae5; color: #065f46; }
    .quality-mid { background: #fef3c7; color: #92400e; }
    .quality-low { background: #fee2e2; color: #991b1b; }
    .status-present { color: #059669; font-weight: 600; }
    .status-missing { color: #dc2626; font-weight: 600; }
    .status-pending { color: #d97706; font-weight: 600; }
    .status-conflict { color: #7c3aed; font-weight: 600; }
    div[data-testid="stSidebar"] { background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%); }
    .compare-box {
        background: #f8fafc; color: #0f172a; border: 1px solid #e2e8f0;
        border-radius: 8px; padding: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

FIXTURES_ROOT = ROOT / "fixtures" / "patient_folders"
REAL_FIXTURE_ROOT = ROOT / "fixtures" / "patient_real"
config = load_config()
memory = CorrectionMemory(ROOT / "data" / "correction_memory.db")


def status_class(status: str) -> str:
    return {
        "Present": "status-present",
        "Missing": "status-missing",
        "Pending": "status-pending",
        "Conflict": "status-conflict",
    }.get(status, "")


def quality_class(score: float) -> str:
    if score >= 80:
        return "quality-high"
    if score >= 60:
        return "quality-mid"
    return "quality-low"


def load_manifest() -> list[dict]:
    manifest_path = FIXTURES_ROOT / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("scenarios", [])
    return []


def check_provider(name: str) -> str:
    import os

    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "ollama": "OLLAMA_BASE_URL",
        "huggingface": "HUGGINGFACE_API_TOKEN",
    }
    env_key = key_map.get(name, "")
    return "Ready" if env_key and os.getenv(env_key) else "API key not configured"


providers = [p for p in PROVIDERS if p != "mock"]

with st.sidebar:
    st.header("⚙️ Configuration")
    default_provider = config.get("llm_provider", "anthropic")
    selected_provider = st.selectbox(
        "LLM Provider",
        providers,
        index=providers.index(default_provider) if default_provider in providers else 0,
    )
    status = check_provider(selected_provider)
    (st.success if status == "Ready" else st.warning)(f"{selected_provider}: {status}")

    st.divider()
    st.subheader("📁 Demo Scenarios")
    manifest = load_manifest()
    scenario_names = sorted({s["name"] for s in manifest}) if manifest else []
    selected_sample = st.selectbox(
        "Load fixture",
        [""] + scenario_names,
        format_func=lambda x: "— Pick a scenario —" if x == "" else x,
    )
    if st.button("Load Sample PDFs", use_container_width=True, type="primary") and selected_sample:
        sample_dir = FIXTURES_ROOT / selected_sample
        pdfs = list(sample_dir.glob("*.pdf"))
        if pdfs:
            st.session_state["sample_folder"] = str(sample_dir)
            st.session_state["sample_name"] = selected_sample
            st.success(f"Loaded {len(pdfs)} PDFs from `{selected_sample}`")
        else:
            st.error("No PDFs found")

    st.divider()
    st.subheader("📄 Reviewer Sample")
    st.caption("71-page scanned chart — requires Tesseract OCR (`winget install UB-Mannheim.TesseractOCR`)")
    if tesseract_available():
        st.caption("Tesseract: ready")
    else:
        st.warning("Tesseract not found — scanned uploads will fail OCR")
    if st.button("Load Reviewer Sample", use_container_width=True):
        REAL_FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
        pdfs = list(REAL_FIXTURE_ROOT.glob("*.pdf"))
        if pdfs:
            st.session_state["sample_folder"] = str(REAL_FIXTURE_ROOT)
            st.session_state["sample_name"] = "patient_real"
            st.success(f"Loaded {len(pdfs)} PDF(s) from reviewer folder")
        else:
            st.warning(
                f"No PDF in `{REAL_FIXTURE_ROOT}`. Copy `patient 2 (1).pdf` there — see fixtures/patient_real/README.md"
            )

    st.divider()
    st.caption(f"**{len(scenario_names)}** test scenarios available")
    st.caption("Agent loop → tools → audit → **narrative synthesis** → clinician draft")

st.markdown(
    """
<div class="hero">
  <h1>Clinical Discharge Summary Agent</h1>
  <p>LangGraph agentic pipeline with evidence grounding, safety flags, and attending-style narrative synthesis for clinician review.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(f'<div class="draft-banner">{DRAFT_BANNER}</div>', unsafe_allow_html=True)

col_upload, col_run = st.columns([3, 1])
with col_upload:
    uploaded_files = st.file_uploader(
        "Upload patient PDF folder",
        type=["pdf"],
        accept_multiple_files=True,
        help="One or more PDFs — single 71-page scanned chart OK (requires Tesseract OCR).",
    )
with col_run:
    st.write("")
    st.write("")
    run_clicked = st.button("▶ Run Agent", type="primary", use_container_width=True)

patient_source = "upload" if uploaded_files else ("sample" if st.session_state.get("sample_folder") else None)

if run_clicked and patient_source:
    progress_slot = st.empty()

    def _pdf_progress(current: int, total: int, filename: str) -> None:
        pct = int((current / total) * 100) if total else 0
        progress_slot.info(f"OCR **{filename}** — page {current}/{total} ({pct}%)")

    try:
        with st.status("Running discharge agent pipeline…", expanded=True) as status:
            st.write("Planning → tools → audit → narrative synthesis")
            if patient_source == "upload":
                patient_dir = stage_uploaded_pdfs(uploaded_files)
                st.write(f"Staged {len(list(patient_dir.glob('*.pdf')))} PDF(s) for processing")
            else:
                patient_dir = Path(st.session_state["sample_folder"])

            result = run_discharge_agent(
                patient_dir,
                llm_provider=selected_provider,
                pdf_progress_callback=_pdf_progress,
            )
            status.update(label="Agent run complete", state="complete")

        progress_slot.empty()
        st.session_state["result"] = result
        st.session_state.pop("run_error", None)
        st.success(f"Draft ready — patient `{result.patient_id}` ({len(result.evidence_store.items)} evidence items)")
    except Exception as exc:
        progress_slot.empty()
        st.session_state["run_error"] = str(exc)
        st.error(f"Agent failed: {exc}")

if "result" in st.session_state:
    result = st.session_state["result"]
    quality = evaluate_summary_quality(result.draft_summary, result.evidence_store.to_dict_list())
    qscore = result.draft_summary.quality_score or quality["overall_score"]
    qclass = quality_class(qscore)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Status", result.status)
    m2.markdown(
        f"**Quality**<br><span class='quality-pill {qclass}'>{qscore:.0f}/100</span>",
        unsafe_allow_html=True,
    )
    m3.metric("Safety Flags", len(result.safety_flags))
    m4.metric("Conflicts", len(result.conflicts))
    m5.metric("Review Items", len(result.clinician_review_items))
    m6.metric("Trace Steps", len(result.trace_log))

    tab_narrative, tab_compare, tab_sections, tab_safety, tab_meds, tab_evidence, tab_trace, tab_download = st.tabs(
        [
            "📄 Clinical Narrative",
            "↔ Before / After",
            "📋 Sections",
            "🛡 Safety",
            "💊 Medications",
            "🔍 Evidence",
            "🧠 Agent Trace",
            "⬇ Download",
        ]
    )

    with tab_narrative:
        if result.draft_summary.executive_summary:
            st.subheader("Executive Summary")
            st.info(result.draft_summary.executive_summary)
        if result.draft_summary.narrative_summary:
            st.markdown(result.draft_summary.narrative_summary)
        else:
            st.warning("Narrative document not available.")

        with st.expander("Quality Rubric Breakdown"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Readability", f"{quality['readability']:.0f}")
            c2.metric("Grounding", f"{quality['grounding']:.0f}")
            c3.metric("Safety", f"{quality['safety_compliance']:.0f}")
            c4.metric("Completeness", f"{quality['completeness']:.0f}")
            if quality["issues"]:
                st.write("Issues:", ", ".join(quality["issues"]))

    with tab_compare:
        st.caption("Raw extraction vs synthesized narrative (same evidence, improved readability)")
        compare_sections = [
            s for s in result.draft_summary.sections
            if s.raw_content and s.raw_content != s.content and s.name not in {"Safety Flags", "Conflicts", "Clinician Review Items"}
        ]
        if compare_sections:
            for section in compare_sections[:8]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**{section.name}** — _Extracted_")
                    st.markdown(f"<div class='compare-box'>{section.raw_content}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"**{section.name}** — _Synthesized_")
                    st.markdown(f"<div class='compare-box'>{section.content}</div>", unsafe_allow_html=True)
        else:
            st.info("Run a complete scenario to see before/after narrative improvements.")

    with tab_sections:
        for section in result.draft_summary.sections:
            if section.name in ("Safety Flags", "Conflicts", "Clinician Review Items"):
                continue
            css = status_class(section.status.value)
            st.markdown(f"#### {section.name} <span class='{css}'>[{section.status.value}]</span>", unsafe_allow_html=True)
            st.markdown(section.content)
            st.divider()

    with tab_safety:
        if result.safety_flags:
            for flag in result.safety_flags:
                fn = st.error if flag.severity in ("high", "critical") else st.warning
                fn(f"**{flag.severity.upper()}** · {flag.category}: {flag.message}")
        else:
            st.success("No safety flags.")
        st.subheader("Clinician Review Queue")
        for item in result.clinician_review_items:
            st.info(f"**[{item.priority}]** {item.reason}: {item.details}")

    with tab_meds:
        for change in result.medication_changes:
            icon = "⚠️" if change.requires_review else "✓"
            st.write(
                f"{icon} **{change.medication_name}** — {change.change_type.value}  \n"
                f"Admission: {change.admission_value or '—'} → Discharge: {change.discharge_value or '—'}  \n"
                f"Reason: {change.reason}"
            )

    with tab_evidence:
        st.dataframe(
            [
                {
                    "field": e.field_name,
                    "value": e.value[:80],
                    "document": e.source_document,
                    "page": e.page_number,
                }
                for e in result.evidence_store.items
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tab_trace:
        for step in result.trace_log:
            with st.expander(f"Step {step.step_number}: {step.tool_name} — {step.result}"):
                st.write(step.reasoning_summary)
                if step.tool_output:
                    st.json(step.tool_output)

    with tab_download:
        if result.output_dir:
            st.code(result.output_dir)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            out_path = Path(result.output_dir)
            if out_path.exists():
                for f in out_path.glob("*.json"):
                    zf.writestr(f.name, f.read_text(encoding="utf-8"))
        st.download_button(
            "Download All Results (ZIP)",
            buf.getvalue(),
            file_name=f"discharge_{result.patient_id}.zip",
            use_container_width=True,
        )

else:
    st.info("Upload PDFs or load a demo scenario from the sidebar, then click **Run Agent**.")
    if manifest:
        st.subheader("Demo Scenario Library")
        st.dataframe(
            [{"Scenario": s["name"], "Category": s["category"], "PDFs": s["pdf_count"]} for s in manifest[:25]],
            use_container_width=True,
            hide_index=True,
        )
