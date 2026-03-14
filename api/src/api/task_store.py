"""
Task Store — armazena o estado das tarefas em memória.
Para produção, substitua por Redis ou Supabase.
"""

import uuid
from typing import Any, Dict, Optional

from src.api.schemas import TaskStatus


# Dict global — em produção troque por Redis
_tasks: Dict[str, Dict[str, Any]] = {}


def create_task() -> str:
    """Cria uma nova tarefa e retorna o task_id."""
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {
        "status":      TaskStatus.PENDING,
        "progress":    0.0,
        "message":     "Aguardando processamento...",
        "clips":       [],
        "ai_analysis": None,
        "error":       None,
    }
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    return _tasks.get(task_id)


def update_task(task_id: str, **kwargs):
    """Atualiza campos de uma tarefa existente."""
    if task_id in _tasks:
        _tasks[task_id].update(kwargs)


def all_tasks() -> Dict[str, Dict[str, Any]]:
    return dict(_tasks)
