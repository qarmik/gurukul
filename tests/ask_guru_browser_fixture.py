"""Disposable D01 server for test_ask_guru_browser.cjs; never uses a learner root."""
import json
import sys
import threading

from gurukul.assessment import events
from gurukul.workspace import Server, sample_guru
from test_workspace import WorkspaceTests


def main():
    fixture = WorkspaceTests()
    fixture.setUp()
    calls = []

    def respond(question):
        calls.append(question)
        return sample_guru(question)

    try:
        with Server(fixture.root, fixture.sid, responder=respond) as server:
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            try:
                baseline = len(events(fixture.w.store.db, 'execution.finished'))
                print(json.dumps({'launch': server.origin + '/#' + server.token}), flush=True)
                sys.stdin.read()
            finally:
                server.shutdown()
                worker.join()
            db = fixture.w.store.db
            print(json.dumps({
                'responder_calls': len(calls),
                'executions_before': baseline,
                'executions_after': len(events(db, 'execution.finished')),
                'assessment_reservations': len(events(db, 'assessment.run_reserved')),
                'assessment_openings': len(events(db, 'assessment.opened')),
                'provider_calls': 0,
            }), flush=True)
    finally:
        fixture.tearDown()


if __name__ == '__main__':
    main()
