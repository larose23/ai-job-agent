import pytest
import asyncio
from application_dispatcher import ApplicationDispatcher

class DummySheetsLogger:
    def __init__(self, *args, **kwargs): pass
    def mark_cold_email_sent(self, *a, **k): self.called = 'cold_email'
    def mark_applied(self, *a, **k): self.called = 'applied'
    def update_notes(self, *a, **k): self.called = 'manual_review'

@pytest.mark.asyncio
async def test_dispatcher_cold_email(monkeypatch):
    # Patch dependencies
    monkeypatch.setattr('application_dispatcher.SheetsLogger', DummySheetsLogger)
    monkeypatch.setattr('application_dispatcher.send_cold_email', lambda **kwargs: True)
    monkeypatch.setattr('application_dispatcher.JobApplication', lambda *a, **k: None)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json'}, {'name': 'Test'})
    job = {'recruiter_email': 'test@example.com', 'title': 'A', 'company': 'B', 'job_url': 'url'}
    result = await dispatcher.dispatch(job)
    assert result == 'cold_email'

@pytest.mark.asyncio
async def test_dispatcher_web_form(monkeypatch):
    class DummyJobApp:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def apply_to_job(self, job, user_profile): return True
    monkeypatch.setattr('application_dispatcher.SheetsLogger', DummySheetsLogger)
    monkeypatch.setattr('application_dispatcher.send_cold_email', lambda **kwargs: False)
    monkeypatch.setattr('application_dispatcher.JobApplication', DummyJobApp)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json'}, {'name': 'Test'})
    job = {'apply_url': 'url', 'title': 'A', 'company': 'B', 'job_url': 'url'}
    result = await dispatcher.dispatch(job)
    assert result == 'web_form'

@pytest.mark.asyncio
async def test_dispatcher_manual_review(monkeypatch):
    monkeypatch.setattr('application_dispatcher.SheetsLogger', DummySheetsLogger)
    monkeypatch.setattr('application_dispatcher.send_cold_email', lambda **kwargs: False)
    monkeypatch.setattr('application_dispatcher.JobApplication', lambda *a, **k: None)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json'}, {'name': 'Test'})
    job = {'title': 'A', 'company': 'B', 'job_url': 'url'}
    result = await dispatcher.dispatch(job)
    assert result == 'manual_review'

@pytest.mark.asyncio
def test_dispatcher_flags_auto_apply(monkeypatch):
    class DummyJobApp:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def apply_to_job(self, job, user_profile): return True
    monkeypatch.setattr('application_dispatcher.SheetsLogger', DummySheetsLogger)
    monkeypatch.setattr('application_dispatcher.send_cold_email', lambda **kwargs: False)
    monkeypatch.setattr('application_dispatcher.JobApplication', DummyJobApp)
    # Case 1: auto_apply_enabled=True, review_before_apply=False (should auto-apply)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json', 'auto_apply_enabled': True, 'review_before_apply': False}, {'name': 'Test'})
    job = {'apply_url': 'url', 'title': 'A', 'company': 'B', 'job_url': 'url'}
    result = asyncio.run(dispatcher.dispatch(job))
    assert result == 'web_form'
    # Case 2: auto_apply_enabled=False, review_before_apply=False (should manual review)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json', 'auto_apply_enabled': False, 'review_before_apply': False}, {'name': 'Test'})
    result = asyncio.run(dispatcher.dispatch(job))
    assert result == 'manual_review'
    # Case 3: auto_apply_enabled=True, review_before_apply=True (should manual review)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json', 'auto_apply_enabled': True, 'review_before_apply': True}, {'name': 'Test'})
    result = asyncio.run(dispatcher.dispatch(job))
    assert result == 'manual_review'
    # Case 4: auto_apply_enabled=False, review_before_apply=True (should manual review)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json', 'auto_apply_enabled': False, 'review_before_apply': True}, {'name': 'Test'})
    result = asyncio.run(dispatcher.dispatch(job))
    assert result == 'manual_review'

@pytest.mark.asyncio
def test_dispatcher_review_queue(monkeypatch):
    class DummySheetsLogger:
        def __init__(self, *a, **k): self.called = None
        def append_review_row(self, job): self.called = 'review_queue'
        def mark_cold_email_sent(self, *a, **k): pass
        def mark_applied(self, *a, **k): pass
        def update_notes(self, *a, **k): pass
    monkeypatch.setattr('application_dispatcher.SheetsLogger', DummySheetsLogger)
    monkeypatch.setattr('application_dispatcher.send_cold_email', lambda **kwargs: False)
    monkeypatch.setattr('application_dispatcher.JobApplication', lambda *a, **k: None)
    dispatcher = ApplicationDispatcher({'config_path': 'config.json', 'review_before_apply': True}, {'name': 'Test'})
    job = {'apply_url': 'url', 'title': 'A', 'company': 'B', 'job_url': 'url'}
    result = asyncio.run(dispatcher.dispatch(job))
    assert result == 'review_queue' 