from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import AnalysisSummary, ProcessingResult
from app.services.file_normalizer import to_ocr_image_bytes
from app.services.inspection_engine import InspectionEngine
from app.services.llm import LLMService
from app.services.ocr import OCRService

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr = OCRService(token=settings.hf_token, model=settings.hf_ocr_model)
llm = LLMService(token=settings.hf_token, model=settings.hf_llm_model)
engine = InspectionEngine(threshold=settings.auto_apply_threshold)


@app.get("/", response_class=FileResponse)
def ui() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "threshold": settings.auto_apply_threshold,
        "ocr_model": settings.hf_ocr_model,
        "llm_model": settings.hf_llm_model,
    }


@app.get("/analysis", response_model=AnalysisSummary)
def analysis() -> AnalysisSummary:
    return AnalysisSummary(
        current_state=[
            "Handwritten RGA and rejected-parts forms are manually re-entered into BMS DRET line by line.",
            "Approx. 5 minutes per line creates 95 minutes of effort for a 19-line sample document.",
            "No consistent rejection language and weak digital audit trace for disputes.",
        ],
        future_state=[
            "Warehouse uploads two document images; OCR digitizes all lines in seconds.",
            "Open-source LLM transforms OCR text into structured JSON and standardized rejection reasons.",
            "Lines with confidence >= 80% auto-apply; low-confidence lines route to review queue.",
        ],
        phased_rollout=[
            "Phase 1 Shadow Mode (Months 1-2): AI in parallel, no auto-apply.",
            "Phase 2 Assisted Mode (Months 3-4): human confirm/edit in UI.",
            "Phase 3 Autonomous Mode (Months 5-6): threshold-based auto-apply.",
            "Phase 4 Optimize & Expand (Month 7+): retrain and expand coverage.",
        ],
        approvals_needed=[
            "Approve 80% confidence threshold for auto-apply.",
            "Assign review-queue owner for below-threshold lines.",
            "Confirm CECO-only initial scope.",
            "Nominate warehouse validators for shadow mode.",
        ],
    )


@app.post("/process", response_model=ProcessingResult)
async def process_documents(
    rga_image: UploadFile = File(...),
    rejected_image: UploadFile = File(...),
) -> ProcessingResult:
    rga_bytes = await to_ocr_image_bytes(rga_image)
    rej_bytes = await to_ocr_image_bytes(rejected_image)

    max_size = settings.max_image_size_mb * 1024 * 1024
    if len(rga_bytes) > max_size or len(rej_bytes) > max_size:
        raise HTTPException(status_code=400, detail="One or more files exceed max size limit")

    try:
        rga_text = ocr.image_to_text(rga_bytes)
        rejection_text = ocr.image_to_text(rej_bytes)

        if not rga_text.strip() and not rejection_text.strip():
            raise HTTPException(
                status_code=422,
                detail="No readable text extracted from uploaded files. Use clearer scan/image or different page.",
            )

        prompt = engine.build_prompt(rga_text=rga_text, rejection_text=rejection_text)
        fallback = {"dealer_name": "", "rga_number": "", "lines": []}
        extracted = llm.extract_json(prompt=prompt, fallback=fallback)

        if not extracted.get("lines"):
            extracted = engine.heuristic_extract(rga_text=rga_text, rejection_text=rejection_text)

        return engine.post_process(extracted=extracted, rga_text=rga_text, rejection_text=rejection_text)
    except HTTPException:
        raise
    except Exception as ex:
        reason = str(ex).strip() or type(ex).__name__
        raise HTTPException(status_code=500, detail=f"Processing failed: {reason}") from ex
