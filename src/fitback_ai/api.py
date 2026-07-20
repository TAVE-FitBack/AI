from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .ai_service import (
    analyze_consultation,
    check_consultation_preview,
    check_inquiry_preview,
    generate_message,
    recommend_next_action,
    sync_consultation_graph,
)
from .api_models import (
    ConsultationAnalyzeRequest,
    ConsultationAnalyzeResponse,
    ConsultationGraphSyncRequest,
    ConsultationPreviewRequest,
    GraphSyncResponse,
    InquiryPreviewRequest,
    MessageGenerateRequest,
    MessageGenerateResponse,
    NextActionRequest,
    NextActionResponse,
    PreviewResponse,
)

app = FastAPI(
    title="Fitback AI API",
    version="0.1.0",
    description="FastAPI contract for Fitback Spring Boot AI integration.",
)


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "code": "AI_PROCESSING_FAILED"},
    )


@app.post("/ai/v1/inquiries/check-preview", response_model=PreviewResponse)
def inquiry_check_preview(request: InquiryPreviewRequest) -> PreviewResponse:
    return check_inquiry_preview(request)


@app.post("/ai/v1/consultations/check-preview", response_model=PreviewResponse)
def consultation_check_preview(request: ConsultationPreviewRequest) -> PreviewResponse:
    return check_consultation_preview(request)


@app.post("/ai/v1/consultations/analyze", response_model=ConsultationAnalyzeResponse)
def consultation_analyze(request: ConsultationAnalyzeRequest) -> ConsultationAnalyzeResponse:
    return analyze_consultation(request)


@app.post("/ai/v1/graph/consultations/sync", response_model=GraphSyncResponse)
def consultation_graph_sync(request: ConsultationGraphSyncRequest) -> GraphSyncResponse:
    return sync_consultation_graph(request)


@app.post("/ai/v1/consultations/next-action", response_model=NextActionResponse)
def consultation_next_action(request: NextActionRequest) -> NextActionResponse:
    return recommend_next_action(request)


@app.post("/ai/v1/messages/generate", response_model=MessageGenerateResponse)
def message_generate(request: MessageGenerateRequest) -> MessageGenerateResponse:
    return generate_message(request)
