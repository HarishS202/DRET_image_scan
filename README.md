---
title: Dealer Returns AI Inspection
emoji: 🔍
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Image-to-text + LLM JSON extraction for RGA inspection docs
---

# AI-Powered Dealer Parts Return Inspection (Open-Source POC)

This project implements an end-to-end image-to-text and text-to-JSON pipeline for dealer parts return inspection automation, based on `AI-Powered-Dealer-Parts-Return-Inspection.pptx`.

## What this app does

- Accepts two images:
  - RGA inspection sheet
  - Rejected parts list
- Uses Hugging Face OCR to extract text from both images.
- Uses an open-source LLM (via Hugging Face Inference) to convert OCR text into strict, structured JSON.
- Applies business rules:
  - Rejection code mapping to BMS code
  - Confidence threshold routing (>= 80% auto-apply, else review queue)
- Returns BMS-ready JSON output through API and web UI.

## Architecture

1. OCR layer: Hugging Face `image-to-text` model.
2. Extraction layer: Open-source instruct model generates strict JSON.
3. Rule layer: deterministic mapping + confidence routing.
4. API/UI layer: FastAPI backend and minimal HTML frontend.

## Project structure

- `app/main.py` - API endpoints and app bootstrap
- `app/services/ocr.py` - OCR provider wrapper
- `app/services/llm.py` - LLM JSON extraction wrapper
- `app/services/inspection_engine.py` - business rules and post-processing
- `app/models.py` - Pydantic contracts
- `app/static/index.html` - upload UI and output viewer
- `docs/current_future_state.md` - as-is / to-be analysis

## Cloud-first testing (no office-laptop changes)

Use your personal GitHub and deploy directly to Hugging Face Spaces.

1. Create a new personal GitHub repository and push this project there.
2. In Hugging Face, create a new Space:
   - SDK: Docker
   - Visibility: Private (recommended for business docs)
3. Connect/import your personal GitHub repository into that Space.
4. In Space settings, add Variables/Secrets:
   - `HF_TOKEN` = your Hugging Face token
   - Optional overrides: `HF_OCR_MODEL`, `HF_LLM_MODEL`, `AUTO_APPLY_THRESHOLD`
5. Wait for Space build to complete.
6. Open the Space URL and test by uploading RGA + rejected-list images.

This repo already includes:

- `Dockerfile` for Hugging Face Spaces runtime
- `.dockerignore` to avoid leaking local/env files
- FastAPI app on port `7860` (Spaces compatible)

## Local quick start (optional)

1. Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create env file:

```powershell
Copy-Item .env.example .env
```

3. Set your Hugging Face token in `.env`:

- `HF_TOKEN=...`

4. Run the API:

```powershell
uvicorn app.main:app --reload
```

5. Open:

- `http://127.0.0.1:8000`

## API endpoints

- `GET /health` - runtime config and status
- `GET /analysis` - current/future state summary and rollout view
- `POST /process` - image upload and JSON extraction

`POST /process` form-data keys:

- `rga_image`: image file
- `rejected_image`: image file

## Hugging Face test checklist

After Space is live, validate in this order:

1. Open `/health` and verify models + threshold loaded.
2. Upload one known RGA + rejected-list pair in the UI.
3. Confirm JSON includes:
   - line-level quantities
   - rejection code and mapped BMS code
   - confidence and `auto_apply` decision
4. Verify low-confidence lines are routed with `auto_apply=false`.
5. Compare 3-5 lines against manual expected output for Shadow Mode accuracy tracking.

## Business alignment to requirement deck

- Current state pain points represented: manual re-entry, delays, inconsistency.
- Future state represented: digitization, AI extraction, confidence-based automation.
- Rollout represented: Shadow -> Assisted -> Autonomous -> Optimize.
- Control point represented: 80% confidence threshold for auto-apply.

## Notes for production hardening

- Replace partial A-T code map with complete enterprise lookup table.
- Add authentication, access control, and encrypted audit logging.
- Add persistent staging database for extracted lines and review workflow.
- Add model evaluation and drift monitoring by phase.
- For Vercel deployment, split API into serverless functions and use object storage for uploads.
