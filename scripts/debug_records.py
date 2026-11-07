"""Read-only local diagnostics. Never imported by the daily API."""
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from app.web_research.recording import (read_json, load_record, inspect_record,
    replay, reselect, check_report)


def locate(root, run_id):
    try:
        canonical = str(UUID(run_id))
    except ValueError:
        raise HTTPException(400, detail='INVALID_RUN_ID') from None
    matches = []
    for file in Path(root).glob('*/manifest.json'):
        # Only generated record directories, no caller-provided filesystem paths.
        if file.parent.is_symlink() or file.is_symlink():
            continue
        try:
            if read_json(file).get('runId') == canonical:
                matches.append(file.parent)
        except (ValueError, OSError):
            continue
    if len(matches) != 1:
        raise HTTPException(409 if matches else 404, detail='RECORD_NOT_AVAILABLE')
    return matches[0]


def view(root, run_id):
    path = locate(root, run_id)
    try:
        summary = inspect_record(path)
        _, events = load_record(path)
        # Prompts and raw provider responses are not part of the browser view.
        details = []
        for event in events:
            if event['event'] in {'session_end', 'execution_error'}:
                continue
            data = dict(event['data'])
            if 'request' in data:
                data['input'] = data.pop('request')['data']
                data.pop('input_hash', None)
            details.append({'event':event['event'], 'elapsedMs':event['elapsedMs'], 'data':data})
        return {**summary, 'details':details}
    except Exception:
        raise HTTPException(409, detail='RECORD_INCOMPLETE_OR_DAMAGED') from None


def review(root, run_id, action):
    functions = {'session':replay, 'select':reselect, 'report-check':check_report}
    if action not in functions:
        raise HTTPException(400, detail='INVALID_REVIEW_ACTION')
    path = locate(root, run_id)
    try:
        result = functions[action](path)
        if action == 'session':
            session = result['session']
            return {'action':action, 'externalRequests':0,
                    'status':session['outcome']['status'] if session['outcome'] else 'FAILED',
                    'stopReason':session['stop_reason'], 'codeChanged':result['codeChanged']}
        return {'action':action, **result}
    except Exception:
        raise HTTPException(409, detail='REVIEW_UNAVAILABLE') from None
