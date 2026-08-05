"""
api/routers/eval.py
────────────────────
Evaluation endpoints:

  POST /api/eval/run           Run the full evaluation suite (slow, ~5 min)
  GET  /api/eval/{repo_id}/latest  Get latest eval results for a repo

The evaluation uses the same evaluate.py pipeline that already exists.
We wrap it in a FastAPI endpoint and SSE stream the progress.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.eval import RunEvalRequest, EvalSummaryResponse
from api.services import supabase_service
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

            # Run evaluation in executor (blocking)
            from app.llm.llm_client import configure_llamaindex_settings

            configure_llamaindex_settings()

            yield f"data: {json.dumps({'type': 'progress', 'message': 'LLM and evaluators loaded. Running queries...'})}\n\n"

            # Import evaluate module from project root
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

            from evaluate import run_evaluation as _run_eval, EvalSummary
            from dataclasses import asdict

            progress_messages = []

            def _run():
                return _run_eval(index_name)

            summary = await asyncio.get_event_loop().run_in_executor(None, _run)

            if summary is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Evaluation returned no results.'})}\n\n"
                return

            summary_dict = asdict(summary)

            yield f"data: {json.dumps({'type': 'progress', 'message': f'Completed {summary.total_queries} queries. Saving results...'})}\n\n"

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

    return EvalSummaryResponse(
        id=eval_record.get("id"),
        repo_id=repo_id,
        hit_rate=eval_record.get("hit_rate", 0.0),
        mrr=eval_record.get("mrr", 0.0),
        avg_faithfulness=eval_record.get("avg_faithfulness", 0.0),
        avg_relevancy=eval_record.get("avg_relevancy", 0.0),
        mode_accuracy=eval_record.get("mode_accuracy", 0.0),
        avg_latency_total=eval_record.get("avg_latency_total", 0.0),
        avg_latency_retrieval=eval_record.get("avg_latency_retrieval", 0.0),
        avg_latency_rerank=eval_record.get("avg_latency_rerank", 0.0),
        avg_latency_llm=eval_record.get("avg_latency_llm", 0.0),
        colbert_enabled=eval_record.get("colbert_enabled", False),
        total_queries=eval_record.get("result_json", {}).get("total_queries", 0),
        created_at=eval_record.get("created_at"),
    )
