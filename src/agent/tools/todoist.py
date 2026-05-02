"""Todoist task management tools."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool


def create_todoist_tools(token: str) -> list[BaseTool]:
    """Return Todoist tools bound to the given API token."""
    from todoist_api_python.api import TodoistAPI

    api = TodoistAPI(token)

    @tool
    def list_tasks(filter: str = "") -> str:
        """Todoist 할일 목록을 조회한다. filter에 'today', 'overdue', '7 days' 등 Todoist 필터 문법을 사용할 수 있다."""
        try:
            tasks = api.get_tasks(filter=filter or None)
            if not tasks:
                return "할일이 없습니다."
            lines = []
            for t in tasks[:20]:
                due = t.due.string if t.due else "없음"
                lines.append(f"[{t.id}] {t.content} (마감: {due})")
            return "\n".join(lines)
        except Exception as e:
            return f"조회 실패: {e}"

    @tool
    def add_task(content: str, due_string: str = "") -> str:
        """Todoist에 할일을 추가한다. due_string에 '내일', '다음 주 월요일' 등 자연어 마감일을 지정할 수 있다."""
        try:
            kwargs: dict = {"content": content}
            if due_string:
                kwargs["due_string"] = due_string
            task = api.add_task(**kwargs)
            return f"추가됨: [{task.id}] {task.content}"
        except Exception as e:
            return f"추가 실패: {e}"

    @tool
    def complete_task(task_id: str) -> str:
        """Todoist 할일을 완료 처리한다. task_id는 list_tasks로 확인한다."""
        try:
            api.close_task(task_id=task_id)
            return f"완료 처리됨: {task_id}"
        except Exception as e:
            return f"완료 처리 실패: {e}"

    @tool
    def delete_task(task_id: str) -> str:
        """Todoist 할일을 삭제한다. task_id는 list_tasks로 확인한다."""
        try:
            api.delete_task(task_id=task_id)
            return f"삭제됨: {task_id}"
        except Exception as e:
            return f"삭제 실패: {e}"

    return [list_tasks, add_task, complete_task, delete_task]
