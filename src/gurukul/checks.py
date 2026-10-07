"""D01 evidence checks. Never exec/eval or rerun learner code."""
import ast
import json
from pathlib import Path
from .store import canonical, now
from .submissions import inspect, digest


class NeedsReview(Exception):
    pass


class UndefinedName(Exception):
    def __init__(self, node):
        self.node = node


def literal(node, values):
    if isinstance(node, ast.Constant) and type(node.value) in (str, int, float):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise UndefinedName(node)
        return values[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = literal(node.operand, values)
        if type(value) in (int, float):
            return -value if isinstance(node.op, ast.USub) else value
    raise NeedsReview('Expression is outside the D01 checker subset.')


def analyse(source):
    tree = ast.parse(source)
    values, first_types, generations, printed = {}, {}, {}, set()
    initial_values = {}
    changed_after_print, reprinted = set(), set()
    output = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and all(isinstance(t, ast.Name) for t in statement.targets):
            value = literal(statement.value, values)
            for target in statement.targets:
                name = target.id
                if name == 'print':
                    raise NeedsReview('Rebinding print requires review.')
                if name not in values:
                    initial_values[name] = value
                    first_types[name] = 'str' if type(value) is str else 'number'
                    generations[name] = 0
                else:
                    if name in printed and (type(value) is not type(values[name]) or value != values[name]):
                        changed_after_print.add(name)
                    generations[name] += 1
                values[name] = value
        elif (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
              and isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'print'):
            call = statement.value
            formatting = {'sep': ' ', 'end': '\n'}
            for keyword in call.keywords:
                if keyword.arg not in formatting or not isinstance(keyword.value, ast.Constant) or type(keyword.value.value) is not str:
                    raise NeedsReview('Only literal sep/end print options are supported.')
                formatting[keyword.arg] = keyword.value.value
            args = [literal(arg, values) for arg in call.args]
            for arg in call.args:
                if isinstance(arg, ast.Name):
                    if generations[arg.id] == 0:
                        printed.add(arg.id)
                    if (arg.id in changed_after_print and
                            (type(values[arg.id]) is not type(initial_values[arg.id])
                             or values[arg.id] != initial_values[arg.id])):
                        reprinted.add(arg.id)
            output.append(formatting['sep'].join(str(value) for value in args) + formatting['end'])
        else:
            raise NeedsReview('Statement is outside the D01 checker subset.')
    return {'tree': tree, 'variables': len(values), 'types': {first_types[name] for name in printed},
            'initial_prints': len(printed), 'reprinted': len(reprinted), 'stdout': ''.join(output)}


def check_item(check_id, condition, detail):
    return {'id': check_id, 'status': 'PASS' if condition else 'FAIL', 'detail': detail}


def snapshot(store, attempt_id):
    attempt = inspect(store, attempt_id)
    raw = (store.state_dir / 'evidence' / attempt_id / 'submission.py').read_bytes()
    if digest(raw) != attempt['source_sha256']:
        raise ValueError('Submission snapshot integrity failure.')
    return attempt, raw


def exercise_for_attempt(store, attempt):
    row = store.db.execute('''SELECT e.* FROM exercises e JOIN sessions s
        ON s.exercise_id=e.id AND s.exercise_version=e.version WHERE s.id=?''',
        (attempt['session_id'],)).fetchone()
    if row is None or digest(row['content_json'].encode('utf-8')) != row['sha256']:
        raise ValueError('Stored exercise integrity failure; check refused.')
    return dict(row)


def repair_evidence(store, repaired, source, failed, failed_source):
    if failed['session_id'] != repaired['session_id']:
        return check_item('quoted_text_repair', False, 'Failed attempt belongs to a different session.')
    order = store.db.execute('''SELECT event_type, subject_id, sequence FROM events
        WHERE (event_type='execution.finished' AND subject_id=?)
           OR (event_type='execution.submitted' AND subject_id=?)''',
        (failed['id'], repaired['id'])).fetchall()
    finished = [r['sequence'] for r in order if r['event_type'] == 'execution.finished']
    submitted = [r['sequence'] for r in order if r['event_type'] == 'execution.submitted']
    if not finished or not submitted or finished[0] >= submitted[0]:
        return check_item('quoted_text_repair', False, 'Failed run must finish before the repaired submission.')
    if failed['status'] != 'program_error' or 'NameError:' not in failed['execution']['stderr']:
        return check_item('quoted_text_repair', False, 'Earlier result is not a captured NameError.')
    missing = None
    try:
        analyse(failed_source)
    except UndefinedName as exc:
        missing = exc.node
    except (NeedsReview, ValueError, RecursionError):
        return {'id': 'quoted_text_repair', 'status': 'REVIEW',
                'detail': 'Earlier failure uses syntax outside the supported repair analysis.'}
    except SyntaxError:
        pass
    if missing is None:
        return check_item('quoted_text_repair', False, 'No supported undefined-name failure was found.')
    tree = ast.parse(failed_source)
    replacements = 0
    # Only an entire bare-name assignment RHS, not an arbitrary NameError.
    for statement in tree.body:
        if (isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Name)
                and statement.value.lineno == missing.lineno
                and statement.value.col_offset == missing.col_offset):
            statement.value = ast.Constant(value=missing.id)
            replacements += 1
    match = replacements == 1 and ast.dump(tree) == ast.dump(ast.parse(source))
    if not match:
        return {'id': 'quoted_text_repair', 'status': 'REVIEW',
                'detail': 'The snapshots differ beyond a single supported quoted-text repair; review is required.'}
    return check_item('quoted_text_repair', True,
                      'Earlier bare-name failure is repaired by quoting the same text; comments/spacing may differ.')


def evaluate(store, attempt_id, root, failed_attempt_id=None):
    attempt, source = snapshot(store, attempt_id)
    exercise = exercise_for_attempt(store, attempt)
    spec_bytes = (Path(root) / 'content/checks/d01-v1.json').read_bytes()
    spec = json.loads(spec_bytes)
    failed, failed_source = (snapshot(store, failed_attempt_id) if failed_attempt_id else (None, None))
    checker_sha = digest(Path(__file__).read_bytes())
    context = {'attempt_id': attempt_id, 'source_sha256': attempt['source_sha256'],
               'exercise_id': exercise['id'], 'exercise_version': exercise['version'],
               'exercise_sha256': exercise['sha256'], 'checker_id': spec['checker_id'],
               'checker_version': spec['checker_version'], 'checker_sha256': checker_sha,
               'spec_sha256': digest(spec_bytes), 'execution_sha256': digest(canonical(attempt['execution']).encode()),
               'failed_attempt_id': failed_attempt_id,
               'failed_source_sha256': failed['source_sha256'] if failed else None,
               'failed_execution_sha256': digest(canonical(failed['execution']).encode()) if failed else None}
    evaluation_id = digest(canonical(context).encode())
    checks = []
    supported = (exercise['id'] == spec['checker_id'] and
                 spec['exercise_hashes'].get(str(exercise['version'])) == exercise['sha256'])
    outcome = None
    if not supported:
        outcome = 'NEEDS_REVIEW'
        checks.append({'id': 'supported_exercise', 'status': 'REVIEW', 'detail': 'Exercise identity/version/hash is not supported by this checker.'})
    elif attempt['status'] not in ('completed', 'program_error'):
        outcome = 'BLOCKED'
        checks.append({'id': 'execution_available', 'status': 'BLOCKED', 'detail': 'A complete execution is required; timeout, capture limits and infrastructure problems do not establish correctness.'})
    else:
        checks.append(check_item('execution_success', attempt['status'] == 'completed' and attempt['execution']['exit_code'] == 0,
                                 'Saved execution must finish with exit code zero.'))
        try:
            evidence = analyse(source)
            checks.extend([
                check_item('five_variables', evidence['variables'] >= spec['minimum_variables'], f"Observed {evidence['variables']} distinct assigned names."),
                check_item('text_and_numbers', set(spec['required_initial_types']) <= evidence['types'], 'Printed initial assignments must include text and numeric values.'),
                check_item('print_initial_values', evidence['initial_prints'] >= spec['minimum_variables'], f"Observed initial-value prints for {evidence['initial_prints']} names."),
                check_item('reassign_and_reprint', evidence['reprinted'] >= spec['minimum_reassigned_and_reprinted'], f"Observed changed values printed after initial values for {evidence['reprinted']} names."),
                check_item('output_matches', evidence['stdout'] == attempt['execution']['stdout'], 'Saved stdout must match independently derived output for this source.')])
            if failed is None:
                checks.append({'id': 'quoted_text_repair', 'status': 'MISSING', 'detail': 'Supply --failed-attempt with the earlier unquoted-text failure.'})
            else:
                checks.append(repair_evidence(store, attempt, source, failed, failed_source))
        except (SyntaxError, UndefinedName) as exc:
            checks.append(check_item('valid_program', False, 'Source has a syntax error or unresolved name.'))
        except (NeedsReview, ValueError, RecursionError) as exc:
            checks.append({'id': 'supported_syntax', 'status': 'REVIEW', 'detail': str(exc)})
        statuses = {check['status'] for check in checks}
        outcome = ('FAIL' if 'FAIL' in statuses else 'NEEDS_REVIEW' if 'REVIEW' in statuses
                   else 'NEEDS_EVIDENCE' if 'MISSING' in statuses else 'CHECKS_PASS')
    result = dict(context, evaluation_id=evaluation_id, outcome=outcome, checks=checks,
                  grants_mastery=False, independence='not_verified',
                  not_verified=spec['unverifiable'])
    return store.record_evaluation(evaluation_id, attempt, result, now())
