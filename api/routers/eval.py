"""
api/routers/eval.py
────────────────────
Evaluation endpoints:

  POST /api/eval/run           Run the full evaluation suite (slow, ~5 min)
  GET  /api/eval/{repo_id}/latest  Get latest eval results for a repo

The evaluation uses the same evaluate.py pipeline that already exists.
We wrap it in a FastAPI endpoint and SSE stream the progress.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.eval import (
    RunEvalRequest,
    EvalSummaryResponse,
    EvalHistoryResponse,
    EvalComparisonResponse,
)
from api.services import supabase_service, evaluation_center_service
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/run")
async def run_evaluation(
    body: RunEvalRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Run the full evaluation suite against an indexed repository.
    Streams progress events via SSE — evaluation takes 3–10 minutes.

    SSE events:
        data: {"type": "progress", "message": "Running query 3/10..."}
        data: {"type": "result", "summary": {...}}
        data: {"type": "done"}
        data: {"type": "error", "message": "..."}

    Note: This is CPU/LLM intensive. Don't run concurrently for the same repo.
    """
    # Verify repo access
    repo = supabase_service.get_repo(supabase, body.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    request_index_name = (body.index_name or "").strip()
    repo_index_name = (repo.get("index_name") or "").strip()
    index_name = request_index_name or repo_index_name
    if not index_name:
        raise HTTPException(
            status_code=400,
            detail="Repository has no valid index_name. Re-index the repository before running evaluation.",
        )

    async def eval_generator():
        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Initialising evaluation suite...'})}\n\n"

            progress_buffer: list[str] = []

            def _emit(message: str) -> None:
                progress_buffer.append(message)

            summary_dict = await evaluation_center_service.run_evaluation_center(
                supabase=supabase,
                repo=repo,
                repo_id=body.repo_id,
                user_id=user_id,
                index_name=index_name,
                mode=body.mode,
                requested_branch=body.branch,
                requested_commit=body.commit_sha,
                embedding_version=body.embedding_version,
                retrieval_settings=body.retrieval_settings,
                prompt_version=body.prompt_version,
                static_confidence_threshold=body.static_confidence_threshold,
                emit_progress=_emit,
            )

            for msg in progress_buffer:
                yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Saving evaluation results...'})}\n\n"

            # Persist to Supabase
            try:
                supabase_service.save_evaluation(
                    supabase,
                    repo_id=body.repo_id,
                    user_id=user_id,
                    summary=summary_dict,
                )
            except Exception as db_err:
                logger.warning(f"Failed to save eval to DB: {db_err}")

            saved = supabase_service.get_latest_evaluation(supabase, body.repo_id)
            if saved:
                summary_dict = evaluation_center_service.hydrate_eval_response(saved)

            yield f"data: {json.dumps({'type': 'result', 'summary': summary_dict})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        eval_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{repo_id}/latest", response_model=Optional[EvalSummaryResponse])
async def get_latest_evaluation(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Return the most recent evaluation results for a repository."""
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    eval_record = supabase_service.get_latest_evaluation(supabase, repo_id)
    if not eval_record:
        return None

    return EvalSummaryResponse(**evaluation_center_service.hydrate_eval_response(eval_record))


@router.get("/{repo_id}/history", response_model=EvalHistoryResponse)
async def get_evaluation_history(
    repo_id: str,
    limit: int = Query(default=30, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    rows = supabase_service.get_recent_evaluations(supabase, repo_id=repo_id, limit=limit)
    points = evaluation_center_service.build_eval_history_points(rows)
    return EvalHistoryResponse(repo_id=repo_id, points=points)


@router.get("/{repo_id}/compare", response_model=EvalComparisonResponse)
async def compare_evaluations(
    repo_id: str,
    baseline_eval_id: Optional[str] = None,
    current_eval_id: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    current_row = (
        supabase_service.get_evaluation_by_id(supabase, repo_id=repo_id, evaluation_id=current_eval_id)
        if current_eval_id
        else supabase_service.get_latest_evaluation(supabase, repo_id)
    )
    if not current_row:
        return EvalComparisonResponse(repo_id=repo_id, current=None, baseline=None, comparison=None)

    if baseline_eval_id:
        baseline_row = supabase_service.get_evaluation_by_id(supabase, repo_id=repo_id, evaluation_id=baseline_eval_id)
    else:
        recent = supabase_service.get_recent_evaluations(supabase, repo_id=repo_id, limit=2)
        baseline_row = recent[1] if len(recent) > 1 else None

    current_summary = evaluation_center_service.hydrate_eval_response(current_row)
    baseline_summary = evaluation_center_service.hydrate_eval_response(baseline_row) if baseline_row else None
    comparison = (
        evaluation_center_service.build_comparison_payload(current_row, baseline_row)
        if baseline_row
        else None
    )

    return EvalComparisonResponse(
        repo_id=repo_id,
        current=EvalSummaryResponse(**current_summary),
        baseline=EvalSummaryResponse(**baseline_summary) if baseline_summary else None,
        comparison=comparison,
    )
