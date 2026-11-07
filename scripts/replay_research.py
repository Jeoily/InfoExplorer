"""Local explicit replay CLI. No model credentials, providers, network or writes to the DB."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend/agent-service/.web-deps'),str(ROOT/'backend/agent-service')]
from app.web_research.recording import inspect_record, replay, reselect, report_input, check_report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['inspect','session','select','report-input','report-check'])
    parser.add_argument('record',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    functions={'inspect':inspect_record,'session':replay,'select':reselect,
               'report-input':report_input,'report-check':check_report}
    try:
        result=functions[args.action](args.record)
        raw=json.dumps(result,ensure_ascii=False,indent=2)
        if args.output:
            # Never replace an earlier result or source record silently.
            with args.output.open('x',encoding='utf-8') as stream:
                stream.write(raw)
            print('REPLAY_OK output='+str(args.output))
        else:
            print(raw)
        return 0
    except Exception as error:
        from app.web_research.recording import ReplayError
        print(json.dumps({'ok':False,'code':str(error) if isinstance(error,ReplayError) else 'REPLAY_FAILED'}))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
