"""Run-scoped immutable citation identities, independent of ranking order."""
from dataclasses import replace
import hashlib
import json

from app.web_research.selection import Passage


class EvidenceRegistry:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._ids: dict[str, str] = {}

    def bind(self, passages: tuple[Passage, ...]) -> tuple[Passage, ...]:
        result = []
        for passage in passages:
            identity = [self.run_id, passage.source_id, passage.paragraph_index,
                        passage.offset_utf16, passage.content_hash]
            key = hashlib.sha256(json.dumps(identity, ensure_ascii=False,
                separators=(',', ':')).encode('utf-8')).hexdigest()
            if key not in self._ids:
                # Two selected sets, up to eight each. Finish must not invent a third set.
                if len(self._ids) >= 16:
                    raise ValueError('Evidence identity limit exceeded')
                self._ids[key] = f'E{len(self._ids) + 1}'
            result.append(replace(passage, evidence_id=self._ids[key], evidence_key=key))
        return tuple(result)
