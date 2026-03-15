"""
GET /api/status/{task_id}        → snapshot atual (compatibilidade)
GET /api/status/{task_id}/stream → SSE — servidor empurra só quando muda

Com SSE o app abre UMA conexão e fica escutando.
A API só escreve quando o status ou progresso mudam — sem ping a cada 5s.
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from src.api.schemas import TaskStatusResponse, TaskStatus, ClipResult
from src.api.task_store import get_task, all_tasks

router = APIRouter(prefix="/status", tags=["Status"])

# Intervalo máximo de espera entre checks internos (ms)
# Baixo o suficiente para capturar transições rápidas sem usar CPU
_POLL_INTERVAL = 0.5   # 500 ms — interno, nunca vira request HTTP


# ──────────────────────────────────────────────────────────────────
#  SNAPSHOT — mantido para compatibilidade e debug
# ──────────────────────────────────────────────────────────────────

@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    summary="Snapshot do estado atual de uma tarefa",
)
async def get_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarefa '{task_id}' não encontrada.",
        )
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        clips=[ClipResult(**c) for c in task.get("clips", [])],
        ai_analysis=task.get("ai_analysis"),
        error=task.get("error"),
    )


# ──────────────────────────────────────────────────────────────────
#  SSE — stream de eventos (uma conexão, zero ping)
# ──────────────────────────────────────────────────────────────────

@router.get(
    "/{task_id}/stream",
    summary="SSE — recebe updates em tempo real sem polling",
    response_class=StreamingResponse,
)
async def stream_status(task_id: str, request: Request):
    """
    Abre uma conexão SSE e envia um evento JSON cada vez que
    status ou progresso mudam. Fecha automaticamente quando
    a tarefa chega em 'done' ou 'error', ou quando o cliente
    desconecta.

    Formato de cada evento:
        data: {"status": "...", "progress": 0.0, "message": "...", "clips": [...], "error": null}
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarefa '{task_id}' não encontrada.",
        )

    async def _gerador():
        ultimo_status   = None
        ultimo_progress = None

        while True:
            # Cliente desconectou — para de gerar
            if await request.is_disconnected():
                break

            task = get_task(task_id)
            if not task:
                break

            status_atual   = task["status"]
            progress_atual = round(float(task.get("progress", 0.0)), 3)

            # Só emite se algo mudou
            if status_atual != ultimo_status or progress_atual != ultimo_progress:
                ultimo_status   = status_atual
                ultimo_progress = progress_atual

                payload = {
                    "task_id":  task_id,
                    "status":   status_atual,
                    "progress": progress_atual,
                    "message":  task.get("message", ""),
                    "clips":    task.get("clips", []),
                    "error":    task.get("error"),
                }
                yield f"data: {json.dumps(payload)}\n\n"

                # Tarefa terminal — fecha o stream
                if status_atual in (TaskStatus.DONE, TaskStatus.ERROR):
                    break

            await asyncio.sleep(_POLL_INTERVAL)

    return StreamingResponse(
        _gerador(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering":"no",   # desativa buffer no nginx
        },
    )


# ──────────────────────────────────────────────────────────────────
#  DEBUG
# ──────────────────────────────────────────────────────────────────

@router.get("/", summary="Lista tarefas (debug)", include_in_schema=False)
async def list_tasks():
    return all_tasks()
