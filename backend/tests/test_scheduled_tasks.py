import asyncio
import threading
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api import scheduled
from app.models.scheduled_task import ScrapeHistory, TaskStatus


class FrozenMonthEnd(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 31, 23, 30)


def test_scheduler_next_run_handles_month_end(monkeypatch):
    from app.core import scheduler

    monkeypatch.setattr(scheduler, "datetime", FrozenMonthEnd)

    assert scheduler._calculate_next_run("09:00") == datetime(2026, 8, 1, 9, 0)


@pytest.mark.asyncio
async def test_run_now_timeout_always_finishes_history(monkeypatch):
    task = SimpleNamespace(
        id="task-1",
        name="timeout-task",
        custom_url="https://example.com",
        scrape_range="1d",
        schedule_time="09:00",
        last_run_at=None,
        next_run_at=None,
        get_source_ids_list=lambda: [],
    )

    api_db = MagicMock()
    api_db.query.return_value.filter.return_value.first.side_effect = [task, None]
    api_db.refresh.side_effect = lambda obj: setattr(obj, "id", "history-1")

    history_obj = MagicMock(spec=ScrapeHistory)
    worker_db = MagicMock()
    worker_db.query.return_value.filter.return_value.first.return_value = history_obj
    session_factory = MagicMock(return_value=worker_db)

    class SlowScraper:
        async def deep_scrape(self, **kwargs):
            await asyncio.sleep(0.05)

        def save_to_database(self, *args, **kwargs):
            return False, None

    monkeypatch.setattr("app.core.database.get_session_local", lambda: session_factory)
    monkeypatch.setattr("app.services.scraper.get_scraper", lambda: SlowScraper())
    monkeypatch.setattr(scheduled, "IMMEDIATE_URL_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(scheduled, "IMMEDIATE_TASK_MAX_RUNTIME_SECONDS", 0.001)
    def run_in_worker_thread(fn):
        worker = threading.Thread(target=fn)
        worker.start()
        worker.join()
        return worker

    monkeypatch.setattr(scheduled._immediate_executor, "submit", run_in_worker_thread)

    response = await scheduled.run_task_now("task-1", db=api_db)

    assert response["history_id"] == "history-1"
    assert history_obj.status == TaskStatus.FAILED.value
    assert history_obj.finished_at is not None
    assert "超时" in history_obj.error_message
    worker_db.commit.assert_called_once()
    worker_db.close.assert_called_once()
