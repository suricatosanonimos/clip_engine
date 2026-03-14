"""
GET /api/status/{task_id}
Retorna o estado atual de uma tarefa de processamento.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import TaskStatusResponse, TaskStatus, ClipResult
from src.api.task_store import get_task, all_tasks

router = APIRouter(prefix="/status", tags=["Status"])


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    summary="Consulta o progresso de uma tarefa",
)
async def get_status(task_id: str):
    """
    Retorna o estado atual da tarefa identificada por **task_id**.

    - `status`: pending | downloading | processing | transcribing | analyzing | done | error
    - `progress`: float de 0.0 a 1.0
    - `clips`: lista de clipes prontos (preenchida quando status = done)
    - `ai_analysis`: resultado da Brain IA (preenchido quando disponível)
    - `error`: mensagem de erro (preenchida quando status = error)
    """
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


@router.get(
    "/",
    summary="Lista todas as tarefas (debug)",
    include_in_schema=False,   # oculto no Swagger em produção
)
async def list_tasks():
    """Lista todas as tarefas em memória — útil apenas em desenvolvimento."""
    return all_tasks()
