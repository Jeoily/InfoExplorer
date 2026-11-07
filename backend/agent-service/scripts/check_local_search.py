"""Explicit public-query smoke check; never run by ordinary pytest."""
import argparse
import json

from app.web_research.content import read_content
from app.web_research.pipeline import ToolFailure
from app.web_research.searxng import SearxngSearch, SearxngSettings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--language', choices=('en-US', 'zh-CN'), default='en-US')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required: this sends a fixed public query to search engines')
    query = 'Python documentation' if args.language == 'en-US' else 'Python 官方文档'
    if args.extract:
        query = 'Python http.client documentation'
    try:
        batch = SearxngSearch(SearxngSettings('http://127.0.0.1:8888', args.language)).search(query)
        result = {'status': 'passed' if batch.candidates else 'empty',
                  'language': args.language, 'candidates': len(batch.candidates),
                  'warnings': batch.warnings,
                  'engines': sorted({e for c in batch.candidates for e in c.engines})}
        if args.extract:
            # Only read the known public documentation host in this smoke check.
            candidate = next((c for c in batch.candidates if c.host == 'docs.python.org'), None)
            if candidate is None:
                result['extraction'] = 'skipped_no_documentation_candidate'
                print(json.dumps(result, ensure_ascii=True))
                return 1
            try:
                document = read_content(candidate)
            except ToolFailure as error:
                result['extraction'] = {'status': 'failed', 'code': error.code}
                print(json.dumps(result, ensure_ascii=True))
                return 1
            result['extraction'] = {'paragraphs': len(document.paragraphs),
                                    'resolved_url': document.metadata.resolved_url,
                                    'extractor': document.metadata.extractor,
                                    'truncated': document.metadata.truncated}
        print(json.dumps(result, ensure_ascii=True))
        return 0 if batch.candidates else 1
    except ToolFailure as error:
        print(json.dumps({'status': 'failed', 'code': error.code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
