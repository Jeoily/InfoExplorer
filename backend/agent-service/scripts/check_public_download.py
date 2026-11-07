"""Explicit public-page smoke check; never imported by the normal test suite."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.web_research.candidates import parse_searxng
from app.web_research.download import DownloadError, download_html
from app.web_research.url_policy import UrlRejected
from app.web_research.content import read_content
from app.web_research.pipeline import ToolFailure


def main():
    parser = argparse.ArgumentParser(description="Opt-in fixed public Python documentation download; no model or database")
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--extract", action="store_true", help="Also extract real HTML; optional dependency required")
    args = parser.parse_args()
    url = "https://docs.python.org/3.13/library/http.client.html"
    source = parse_searxng(json.dumps({"results": [{"url": url, "title": "Python HTTP client documentation"}]}).encode()).candidates[0]
    try:
        if args.extract:
            result = read_content(source)
            print(json.dumps({"status": "passed", "mode": "download_extract",
                "url": result.metadata.resolved_url, "paragraphs": len(result.paragraphs),
                "extractor": result.metadata.extractor, "truncated": result.metadata.truncated,
                "http_requests": result.metadata.http_requests,
                "retrieved_at": result.metadata.retrieved_at,
                "extracted_text_hash": result.metadata.extracted_text_hash}))
            return 0
        result = download_html(source)
        print(json.dumps({"status": "passed", "url": result.resolved_url,
            "bytes": len(result.html), "media": result.content_type,
            "http_requests": result.http_requests, "retrieved_at": result.retrieved_at}))
    except (DownloadError, UrlRejected, ToolFailure) as error:
        print(json.dumps({"status": "failed", "code": error.code}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
