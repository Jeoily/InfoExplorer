"""Explicitly constructed provider adapter; no route or environment auto-enables it."""
import json

from app.model import ModelError, ModelSettings, bounded_request, _slot
from app.web_research.pipeline import ToolFailure
from app.web_research.research_session import _unique
from app.web_research.diagnostics import rejected


class JsonCompletion:
    def __init__(self, settings: ModelSettings, transport=bounded_request):
        self.settings = settings
        self.transport = transport

    @classmethod
    def from_env(cls):
        # V3 has its own opt-in: enabling web research must not enable Wiki generation.
        settings = ModelSettings.from_env(enabled_variable='INFOEXPLORER_WEB_MODEL_ENABLED')
        if settings is None:
            raise ModelError('MODEL_CONFIG_ERROR')
        return cls(settings)

    def __call__(self, stage, request, timeout):
        if stage not in {'plan', 'review', 'report', 'verify'}:
            raise ToolFailure('MODEL_CONFIG_ERROR')
        if not _slot.acquire(blocking=False):
            raise ToolFailure('MODEL_BUSY')
        failure_category = 'provider_envelope'
        try:
            body = json.dumps({'model': self.settings.model, 'stream': False,
                'max_tokens': {'plan': 1800, 'review': 1800, 'report': 3000, 'verify':3000}[stage],
                'messages': [{'role': 'system', 'content': request['instructions']},
                             {'role': 'user', 'content': json.dumps(request['data'], ensure_ascii=False)}]},
                ensure_ascii=False).encode()
            if len(body) > 98304:
                raise ToolFailure('MODEL_INPUT_TOO_LARGE')
            raw = self.transport(self.settings, body, timeout=timeout)
            if not isinstance(raw, bytes) or len(raw) > 65536:
                raise ValueError('Response limit')
            data = json.loads(raw, object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            choices = data['choices']
            if not isinstance(choices, list) or len(choices) != 1 or choices[0]['finish_reason'] != 'stop':
                failure_category = 'provider_truncated'
                raise ValueError('Incomplete response')
            message = choices[0]['message']
            if message.get('tool_calls') or message.get('function_call') or not isinstance(message['content'], str):
                failure_category = 'provider_tool_call' if message.get('tool_calls') or message.get('function_call') else 'provider_content'
                raise ValueError('Invalid response')
            return message['content'].encode('utf-8')
        except ModelError as error:
            allowed = {'MODEL_TIMEOUT', 'MODEL_UNAVAILABLE', 'MODEL_INVALID_RESPONSE',
                       'MODEL_RATE_LIMITED', 'MODEL_AUTH_ERROR', 'MODEL_CONFIG_ERROR'}
            raise ToolFailure(error.code if error.code in allowed else 'MODEL_UNAVAILABLE') from None
        except ToolFailure:
            raise
        except Exception:
            rejected(stage, failure_category)
            raise ToolFailure('MODEL_INVALID_RESPONSE') from None
        finally:
            _slot.release()
