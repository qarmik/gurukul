"""Offline UI control-flow tests; synthetic turns do not constitute live acceptance."""
import argparse
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hermes_live_teach import conversation_loop, read_answer


class InteractiveTests(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(continue_call='saved-call', source=None, choose_source=False,
                                       runtime_root=Path('/tmp/runtime with spaces'), once=False, verbose=False)
        self.previous = {'teaching': {'explanation': 'Prior explanation.', 'diagnostic_question': 'Prior question?'},
                         'excerpt': 'Synthetic material.', 'parent_call_id': 'saved-call',
                         'parent_event_id': 'event', 'parent_report_sha256': 'hash'}

    def test_two_answers_then_quit_advance_only_verified_turns(self):
        seen = []
        def turn(args):
            prompt, evidence = read_answer(self.previous)
            seen.append((args.continue_call, evidence['learner_answer'], args.displayed_call))
            return {'status': 'PASS', 'call_id': 'turn-' + str(len(seen)), 'parent_ledger_record_verified': True}
        output = io.StringIO()
        with patch('builtins.input', side_effect=['first answer', 'second answer', '/quit']), contextlib.redirect_stdout(output):
            self.assertEqual(0, conversation_loop(self.args, turn))
        self.assertEqual([('saved-call', 'first answer', None), ('turn-1', 'second answer', 'turn-1')], seen)
        self.assertIn('--continue turn-2', output.getvalue())
        self.assertIn("'/tmp/runtime with spaces'", output.getvalue())
        self.assertEqual('saved-call', self.args.continue_call)

    def test_quit_eof_and_control_c_submit_nothing(self):
        for signal, expected in [('/quit', 0), (EOFError(), 0), (KeyboardInterrupt(), 130)]:
            calls = []
            def turn(args):
                read_answer(self.previous)
                calls.append('submitted')
            with self.subTest(signal=signal), patch('builtins.input', side_effect=[signal]), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(expected, conversation_loop(self.args, turn))
                self.assertIn('--continue saved-call', out.getvalue())
            self.assertEqual([], calls)

    def test_invalid_answers_reprompt_without_a_turn(self):
        with patch('builtins.input', side_effect=[' ', 'x' * 4001, 'valid answer']), contextlib.redirect_stdout(io.StringIO()):
            _, evidence = read_answer(self.previous)
        self.assertEqual('valid answer', evidence['learner_answer'])

    def test_failure_stops_without_retry_or_advancing_resume(self):
        for report in [{'status': 'BLOCKED', 'call_id': 'failed'},
                       {'status': 'PASS', 'call_id': 'unverified', 'parent_ledger_record_verified': False}]:
            calls = []
            def turn(args):
                calls.append(args.continue_call)
                return report
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(1, conversation_loop(self.args, turn))
            self.assertEqual(['saved-call'], calls)
            self.assertIn('--continue saved-call', out.getvalue())

    def test_exception_stops_without_retry(self):
        with patch('builtins.input', side_effect=ValueError('corrupt evidence')), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, conversation_loop(self.args, lambda args: read_answer(self.previous)))
        self.assertIn('corrupt evidence', out.getvalue())

    def test_once_retains_single_turn_behavior(self):
        self.args.once = True
        calls = []
        def turn(args):
            calls.append(args.continue_call)
            return {'status': 'PASS', 'call_id': 'new', 'parent_ledger_record_verified': True}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, conversation_loop(self.args, turn))
        self.assertEqual(['saved-call'], calls)
        self.assertIn('--continue new', out.getvalue())

    def test_initial_source_selected_only_once(self):
        self.args.continue_call = None
        self.args.choose_source = True
        seen = []
        def turn(args):
            seen.append((args.continue_call, args.choose_source))
            if len(seen) == 1:
                return {'status': 'PASS', 'call_id': 'initial', 'parent_ledger_record_verified': True}
            return read_answer(self.previous)
        with patch('builtins.input', return_value='/quit'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, conversation_loop(self.args, turn))
        self.assertEqual([(None, True), ('initial', False)], seen)


if __name__ == '__main__':
    unittest.main()
