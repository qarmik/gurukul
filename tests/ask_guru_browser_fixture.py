"""Disposable D01 server for test_ask_guru_browser.cjs; never uses a learner root."""
import json
import sys
from gurukul.assessment import events
from test_workspace import HTTPTests


def main():
    fixture = HTTPTests()
    fixture.setUp()
    calls = []
    followup = 'Why didn’t the first print change?'

    def respond(*, system_prompt, prompt):
        turn = json.loads(prompt.split('GURUKUL CONTEXT JSON:\n')[1].split(
            '\nGURU RESPONSE CONTRACT JSON:', 1)[0])['C_turn']
        calls.append(turn)
        explanation = (fixture.explanation if turn['learner_message'] != followup else
                       'The first print already ran using the value available at that point.')
        return json.dumps(fixture.proposal | {'explanation': explanation})

    try:
        fixture.enable_teaching_pipeline()
        fixture.server.teaching_pipeline.transport = respond
        db = fixture.w.store.db
        baseline = len(events(db, 'execution.finished'))
        print(json.dumps({'launch': fixture.server.origin + '/#' + fixture.server.token}), flush=True)
        sys.stdin.read()
        first, second = calls
        assert first['previous_teaching'] is None and first['recent_exchanges'] == []
        assert second['learner_message'] == followup
        assert second['previous_teaching']['explanation'] == fixture.explanation
        assert [entry['learner_message'] for entry in second['recent_exchanges']] == [first['learner_message']]
        print(json.dumps({
            'responder_calls': len(calls),
            'followup_used_first_exchange': True,
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
