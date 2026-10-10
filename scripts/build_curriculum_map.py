"""Derive a versioned representation from the approved canonical local curriculum."""
import hashlib
import json
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'content/curriculum/v0.8.3.txt'
raw = source.read_bytes()
text = raw.decode()
def section(number, next_number):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(str(number)+'. ') and line.isupper())
    end = next(i for i, line in enumerate(lines) if i > start and line.startswith(str(next_number)+'. ') and line.isupper())
    return '\n'.join(lines[start+1:end]).strip()

stages = {}
for match in re.finditer(r'^(C[0-9]): (.*?)\n(.*?)(?=^C[0-9]: |^9\. GATES)', text, re.M | re.S):
    code, title, body = match.groups()
    stages[code] = {'title': title.split(' (')[0], 'canonical_requirements': body.strip()}
families = re.findall(r'^\d+\. (.+)$', section(6, 7), re.M)
data = {'curriculum_version': '0.8.3', 'canonical_source': 'content/curriculum/v0.8.3.txt',
        'canonical_sha256': hashlib.sha256(raw).hexdigest(),
        'target_role': 'Vendor-Side Regulated Enterprise AI Solutions Architect — Financial Services',
        'target_role_origin': 'GURU-004 pedagogical correction dispatch',
        'graduate_outcome': re.search(r'^Target role: (.+)$', text, re.M).group(1),
        'design_principles': section(1,2), 'two_systems': section(2,3),
        'field_method': section(4,5), 'capability_families': families, 'stages': stages,
        'gate_philosophy': section(9,10), 'human_checkpoints': section(10,11),
        'evidence_philosophy': section(12,13),
        'graduate_standard': text.split('15. GRADUATE STANDARD\n')[1].split('APPENDIX A')[0].strip()}
assert len(stages) == 10 and len(families) == 14
(ROOT / 'content/curriculum/map.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
