#!/usr/bin/env python3
"""Read-only local evidence audit; no API call, credentials or learner text printed."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gurukul.hermes_continuation import load_previous, read_local, call_directory
from gurukul.learner_input import verify, verify_admission


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('call_id')
    args=parser.parse_args()
    state=ROOT/'var/hermes-live'
    config=json.loads((ROOT/'config/hermes-live.json').read_text())
    manifest=json.loads((ROOT/'content/sources.json').read_text())
    # Use the same pinned exercise and ledger verification as teaching continuation.
    exercise=json.loads((ROOT/'content/c0_b01/d01.json').read_text())
    saved=load_previous(state,args.call_id,manifest,config,exercise)
    report=json.loads(read_local(call_directory(state,args.call_id)/'report.json'))
    record=report['continuation']['learner_input']
    semantic=verify(record)
    admission=report['pedagogy_admission']
    verify_admission(admission,semantic)
    print(json.dumps({'input_integrity':'PASS','call_id':args.call_id,
        'raw_sha256':record['raw_sha256'],'normalized_sha256':record['normalized_sha256'],
        'normalization_changed_input':record['raw_input']!=semantic,
        'verified_span_fields':sorted(admission['learner_verified_spans']),
        'conversation_status':admission['conversation_status'],
        'conversational_judgment':admission['judgment'],'answer_admitted':admission['answer_admitted'],
        'mastery_granted':False,'pending_question':saved['teaching']['diagnostic_question']},indent=2))

if __name__=='__main__':main()
