"""Opt-in bounded diagnostics: fixed categories only, never provider content."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from threading import Lock

PATH = Path(__file__).resolve().parents[4] / 'logs' / 'web-model-diagnostics.log'
_lock = Lock()
_logger = logging.getLogger('infoexplorer.model.categories')
_logger.propagate = False
_logger.setLevel(logging.WARNING)
REASONS = {'provider_envelope', 'provider_truncated', 'provider_tool_call', 'provider_content',
           'json_syntax', 'schema', 'payload', 'text_policy', 'references', 'repeated_queries',
           'render_policy', 'stage_policy', 'json_empty', 'json_fenced', 'json_bom',
           'json_trailing', 'json_unterminated', 'review_reason_text', 'review_gap_text',
           'review_coverage_ids', 'review_unsupported_coverage', 'review_finish_queries',
           'review_unjustified_supplement', 'review_repeated_search',
           'report_quote_references', 'report_quote_mismatch',
           'schema_missing', 'schema_length', 'schema_type', 'schema_extra', 'schema_value',
           'report_quote_missing', 'report_quote_unknown_anchor', 'audit_claim_coverage', 'audit_replacement'}


def schema_reason(error):
    """Classify only library error codes, never locations, inputs or messages."""
    errors = error.errors(include_url=False, include_context=False, include_input=False)
    if any(item['type'] == 'missing' and len(item['loc']) == 3
           and item['loc'][0] == 'claims' and item['loc'][2] == 'supportingQuotes' for item in errors):
        return 'report_quote_missing'
    kinds = {item['type'] for item in errors}
    if kinds & {'string_too_short', 'string_too_long', 'too_short', 'too_long'}:
        return 'schema_length'
    if 'missing' in kinds:
        return 'schema_missing'
    if any(kind.endswith('_type') for kind in kinds):
        return 'schema_type'
    if 'extra_forbidden' in kinds:
        return 'schema_extra'
    return 'schema_value'


def json_reason(raw, error):
    """Classify syntax only. Never return provider bytes or parser messages."""
    if not isinstance(raw, bytes):
        return 'json_syntax'
    value = raw.strip()
    if not value:
        return 'json_empty'
    if value.startswith(b'```'):
        return 'json_fenced'
    if value.startswith(b'\xef\xbb\xbf'):
        return 'json_bom'
    if error.msg == 'Extra data':
        return 'json_trailing'
    if error.msg.startswith('Unterminated string'):
        return 'json_unterminated'
    return 'json_syntax'


def rejected(stage, reason):
    if os.environ.get('INFOEXPLORER_MODEL_DIAGNOSTICS', 'false') != 'true':
        return
    if stage not in {'plan', 'review', 'report', 'verify'} or reason not in REASONS:
        return
    try:
        with _lock:
            if not any(isinstance(handler, RotatingFileHandler) for handler in _logger.handlers):
                PATH.parent.mkdir(exist_ok=True)
                handler = RotatingFileHandler(PATH, maxBytes=65536, backupCount=1, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                _logger.addHandler(handler)
            _logger.warning('MODEL_RESPONSE_REJECTED stage=%s reason=%s', stage, reason)
    except OSError:
        pass  # Diagnostics cannot change the result or cause a model retry.
