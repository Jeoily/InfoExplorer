"""Opt-in local public-data records and network-free replay.

Not a resumable execution checkpoint. Invalid model text/HTTP envelopes/secrets
are never recorded. Replay uses typed captured tools, not URL fetching or eval.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
from time import monotonic
from uuid import UUID, uuid4

from app.web_research.budget import BudgetExceeded
from app.web_research.candidates import Candidate, SearchBatch
from app.web_research.pipeline import ToolFailure, _render
from app.web_research.research_session import (run_session, GroundedReportOutput, validate_report,
    build_request, _parse, provider_payload)
from app.web_research.selection import Document, SourceMetadata, select_passages

VERSION = 'research-record-v1'
MAX_FILE = 1024 * 1024
MAX_TOTAL = 16 * MAX_FILE
MAX_EVENTS = 80


class ReplayError(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write_file(path, raw):
    tmp = path.with_suffix('.writing')
    with tmp.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def code_versions():
    here = Path(__file__).parent
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(here.glob('*.py'))}


class Recorder:
    def __init__(self, root, question, language, run_id, mode):
        self.path = Path(root)/uuid4().hex
        self.path.mkdir(parents=True)
        self.started = monotonic()
        self.total = 0
        self.disabled = False
        self.manifest = {'version': VERSION, 'recordId': self.path.name, 'runId': str(UUID(run_id)),
            'mode': mode, 'question': question, 'language': language, 'status': 'RECORDING',
            'createdAt': datetime.now(timezone.utc).isoformat(), 'code': code_versions(),
            'python': platform.python_version(), 'events': []}
        self.save_manifest()

    def save_manifest(self):
        write_file(self.path/'manifest.json', encoded(self.manifest))

    def __call__(self, event, payload):
        if self.disabled:
            return
        try:
            number = len(self.manifest['events'])
            value = {'event': event, 'elapsedMs': round((monotonic()-self.started)*1000), 'data': payload}
            raw = encoded(value)
            if number >= MAX_EVENTS or len(raw) > MAX_FILE or self.total+len(raw) > MAX_TOTAL:
                raise ValueError('RECORD_LIMIT')
            name = f'{number:03}.json'
            write_file(self.path/name, raw)
            self.total += len(raw)
            self.manifest['events'].append({'file': name, 'sha256': hashlib.sha256(raw).hexdigest()})
            self.save_manifest()
        except Exception:
            self.disabled = True
            self.manifest['status'] = 'INCOMPLETE'
            self.manifest['error'] = 'RECORD_WRITE_FAILED'
            try:
                self.save_manifest()
            except Exception:
                pass

    def tool(self, kind, function):
        def wrapped(argument, timeout):
            argument_data = asdict(argument) if kind == 'read' else argument
            self('tool_start', {'kind': kind, 'input': argument_data})
            try:
                from app.web_research.execution_control import tool_call
                output = tool_call(kind, function, argument, timeout)
            except Exception as error:
                code = error.code if isinstance(error, (ToolFailure, BudgetExceeded)) else 'UNEXPECTED_TOOL_ERROR'
                self('tool_end', {'kind': kind, 'status': 'FAILED', 'code': code})
                raise
            expected = SearchBatch if kind == 'search' else Document
            if isinstance(output, expected):
                self('tool_end', {'kind': kind, 'status': 'SUCCEEDED', 'output': asdict(output)})
            else:
                self('tool_end', {'kind': kind, 'status': 'FAILED', 'code': 'INVALID_TOOL_TYPE'})
            return output
        wrapped._records_tools = True
        return wrapped

    def finish(self, session):
        self('session_end', {'session': asdict(session)})
        if not self.disabled:
            self.manifest['status'] = 'COMPLETE'
            self.manifest['researchStatus'] = session.outcome.status if session.outcome else 'FAILED'
            try:
                self.save_manifest()
            except Exception:
                self.disabled = True


def record_run(root, mode, question, language, search, read, complete, **kwargs):
    run_id = kwargs.pop('run_id', None) or str(uuid4())
    recorder = Recorder(root, question, language, run_id, mode)
    recorder.manifest['verifyReport'] = bool(kwargs.get('verify_report', False))
    try:
        session = run_session(question, language, recorder.tool('search', search),
            recorder.tool('read', read), complete, run_id=run_id, observer=recorder, **kwargs)
    except Exception:
        recorder('execution_error', {'code': 'EXECUTION_INTERRUPTED'})
        if not recorder.disabled:
            recorder.manifest['status'] = 'INCOMPLETE'
            recorder.save_manifest()
        raise
    recorder.finish(session)
    return session


def read_json(path):
    if path.stat().st_size > MAX_FILE:
        raise ReplayError('RECORD_TOO_LARGE')
    return json.loads(path.read_text(encoding='utf-8'))


def load_record(path):
    path = Path(path)
    manifest = read_json(path/'manifest.json')
    if manifest.get('version') != VERSION or len(manifest.get('events', [])) > MAX_EVENTS:
        raise ReplayError('RECORD_VERSION_OR_LIMIT')
    events = []
    total = 0
    for i, item in enumerate(manifest['events']):
        if item['file'] != f'{i:03}.json':
            raise ReplayError('INVALID_EVENT_PATH')
        file = path/item['file']
        if file.stat().st_size > MAX_FILE:
            raise ReplayError('RECORD_TOO_LARGE')
        raw = file.read_bytes()
        total += len(raw)
        if total > MAX_TOTAL or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ReplayError('RECORD_HASH_OR_LIMIT')
        events.append(json.loads(raw))
    return manifest, events


def document(value):
    data = dict(value)
    data['paragraphs'] = tuple(data['paragraphs'])
    if data['metadata'] is not None:
        data['metadata'] = SourceMetadata(**data['metadata'])
    return Document(**data)


def batch(value):
    data = dict(value)
    data['candidates'] = tuple(Candidate(**{**c, 'engines': tuple(c['engines'])}) for c in data['candidates'])
    data['warnings'] = tuple(data['warnings'])
    return SearchBatch(**data)


def inspect_record(path):
    manifest, events = load_record(path)
    stages, pending = [], {}
    for event in events:
        data, name = event['data'], event['event']
        if name.endswith('_start'):
            key = data.get('stage', data.get('kind'))
            pending[key] = event['elapsedMs']
        elif name.endswith('_end') and name != 'session_end':
            key = data.get('stage', data.get('kind'))
            start = pending.pop(key, event['elapsedMs'])
            stages.append({'stage': key, 'status': data['status'], 'code': data.get('code'),
                'reason': data.get('reason'), 'durationMs': event['elapsedMs']-start})
        elif name == 'selection':
            stages.append({'stage': 'selection', 'status': 'SUCCEEDED',
                           'documents': len(data['documents']), 'evidence': len(data['evidence'])})
    stages.extend({'stage': key, 'status': 'INCOMPLETE'} for key in pending)
    return {'recordId': manifest['recordId'], 'runId': manifest['runId'], 'mode': manifest['mode'],
        'recordStatus': manifest['status'], 'researchStatus': manifest.get('researchStatus'),
        'codeChanged': manifest['code'] != code_versions(), 'stages': stages}


def reselect(path):
    manifest, events = load_record(path)
    selections = [e['data'] for e in events if e['event'] == 'selection']
    if not selections:
        raise ReplayError('NO_SELECTION_INPUT')
    original = selections[-1]
    result = select_passages([document(d) for d in original['documents']], original['questions'],
                             per_source=original.get('perSource', 2))
    key = lambda p: (p['source_id'], p['paragraph_index'], p['offset_utf16'], p['content_hash'])
    previous = {key(p) for p in original['evidence']}
    current = {key(asdict(p)) for p in result}
    return {'mode': 'offline-reselection', 'recordId': manifest['recordId'], 'externalRequests': 0,
        'codeChanged': manifest['code'] != code_versions(), 'added': [list(k) for k in sorted(current-previous)],
        'removed': [list(k) for k in sorted(previous-current)], 'evidence': [asdict(p) for p in result]}


def report_input(path):
    _, events = load_record(path)
    inputs = [e['data']['request'] for e in events if e['event']=='model_start' and e['data']['stage']=='report']
    if not inputs:
        raise ReplayError('NO_REPORT_INPUT')
    return inputs[-1]


def check_report(path):
    manifest, events = load_record(path)
    final_stage = 'verify' if manifest.get('verifyReport',False) else 'report'
    outputs = [e['data']['output'] for e in events if e['event']=='model_end'
               and e['data']['stage']==final_stage and e['data']['status']=='SUCCEEDED']
    if not outputs:
        raise ReplayError('NO_VALIDATED_REPORT')
    evidence = report_input(path)['data']['evidence']
    if final_stage=='verify':
        from app.web_research.research_session import AuditOutput, apply_audit
        originals=[e['data']['output'] for e in events if e['event']=='model_end'
                   and e['data']['stage']=='report' and e['data']['status']=='SUCCEEDED']
        if not originals:
            raise ReplayError('NO_VALIDATED_REPORT')
        draft=apply_audit(GroundedReportOutput.model_validate(originals[-1]),
            AuditOutput.model_validate(outputs[-1]),{e['id']:e['excerpt'] for e in evidence})
    else:
        draft = GroundedReportOutput.model_validate(outputs[-1])
    checked = validate_report(draft, {e['id']: e['excerpt'] for e in evidence})
    # Rendering expects only evidence IDs, so provide minimal typed ID objects.
    from types import SimpleNamespace
    answer = _render(checked, tuple(SimpleNamespace(evidence_id=e['id']) for e in evidence))
    return {'mode': 'offline-report-validation', 'externalRequests': 0, 'report': draft.model_dump(), 'answer': answer}


def regenerate_report(path, complete, *, reselection=False):
    """One injected completion using frozen evidence. No search/read or implicit provider.

    Caller owns consent/budget for a real completion. This function is not exposed
    as a live CLI command and does not overwrite the original research record.
    """
    manifest, events = load_record(path)
    data = report_input(path)['data']
    if reselection:
        inputs = [e['data'] for e in events if e['event']=='selection']
        if not inputs:
            raise ReplayError('NO_SELECTION_INPUT')
        selected = inputs[-1]
        docs = [document(d) for d in selected['documents']]
        passages = select_passages(docs, selected['questions'], per_source=4)
        from app.web_research.identity import EvidenceRegistry
        passages = EvidenceRegistry(manifest['runId']).bind(passages)
        catalog = {d.source_id:d for d in docs}
        sources = {e['sourceId']:e['source'] for e in data['evidence']}
        evidence = []
        for passage in passages:
            doc = catalog[passage.source_id]
            source = sources.get(passage.source_id)
            if source is None:
                if doc.metadata is None:
                    raise ReplayError('SOURCE_METADATA_MISSING')
                source = {'title':doc.title,'url':doc.metadata.requested_url,'metadata':asdict(doc.metadata)}
            evidence.append({'id':passage.evidence_id,'sourceId':passage.source_id,'excerpt':passage.excerpt,
                'evidenceKey':passage.evidence_key,'source':source})
        data = {**data,'evidence':evidence,'finalCoverageNotRechecked':True}
    request = build_request('report', data, GroundedReportOutput)
    if len(encoded(request)) > 98304:
        raise ReplayError('REPORT_INPUT_LIMIT')
    draft = _parse(complete('report', request, 45), GroundedReportOutput)
    checked = validate_report(draft, {e['id']: e['excerpt'] for e in data['evidence']})
    from types import SimpleNamespace
    answer = _render(checked, tuple(SimpleNamespace(evidence_id=e['id']) for e in data['evidence']))
    return {'mode': 'fixed-evidence-generation', 'parentRecordId': manifest['recordId'],
        'inputHash': digest(data), 'searchRequests': 0, 'readRequests': 0,
        'completionCalls': 1, 'report': draft.model_dump(), 'answer': answer,
        'groundedReport': provider_payload(draft), 'reselected':reselection, 'evidence':data['evidence']}


class ReplayTools:
    def __init__(self, events):
        self.events = [e for e in events if e['event'] in {'tool_start','tool_end','model_start','model_end'}]
        self.index = 0
        self.error = None

    def consume(self, start_type, end_type, identity, argument):
        try:
            start, end = self.events[self.index:self.index+2]
            if start['event'] != start_type or end['event'] != end_type:
                raise ReplayError('REPLAY_EVENT_ORDER')
            data = start['data']
            if data.get('stage', data.get('kind')) != identity:
                raise ReplayError('REPLAY_STAGE_MISMATCH')
            expected = data['request'] if start_type=='model_start' else data['input']
            if digest(expected) != digest(argument):
                raise ReplayError('REPLAY_INPUT_CHANGED')
            self.index += 2
            result = end['data']
        except Exception:
            self.error = 'REPLAY_INPUT_OR_SEQUENCE_MISMATCH'
            raise ReplayError(self.error) from None
        if result['status'] == 'FAILED':
            # Reproduce the fixed failure, not invalid raw model text or elapsed timeout.
            if result['code'].startswith('EXECUTION_'):
                raise BudgetExceeded(result['code'])
            try:
                raise ToolFailure(result['code'])
            except ValueError:
                self.error = 'UNREPLAYABLE_TOOL_FAILURE'
                raise ReplayError(self.error) from None
        return result['output']

    def search(self, query, timeout):
        return batch(self.consume('tool_start','tool_end','search',query))

    def read(self, candidate, timeout):
        return document(self.consume('tool_start','tool_end','read',asdict(candidate)))

    def complete(self, stage, request, timeout):
        return encoded(self.consume('model_start','model_end',stage,request))


def replay(path):
    manifest, events = load_record(path)
    if manifest['status'] != 'COMPLETE':
        raise ReplayError('TRACE_INCOMPLETE')
    tools = ReplayTools(events)
    try:
        result = run_session(manifest['question'],manifest['language'],tools.search,tools.read,tools.complete,
                             run_id=manifest['runId'], verify_report=manifest.get('verifyReport',False))
    except Exception:
        raise ReplayError(tools.error or 'REPLAY_FAILED') from None
    if tools.error or tools.index != len(tools.events):
        raise ReplayError(tools.error or 'REPLAY_EVENTS_UNUSED')
    return {'mode': 'offline-recorded-tools', 'externalRequests': 0,
            'codeChanged': manifest['code'] != code_versions(), 'session': asdict(result)}
