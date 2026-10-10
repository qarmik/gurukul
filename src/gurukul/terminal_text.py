"""Bounded terminal-input hygiene, without interpreting Python or rewriting syntax."""
import re


def normalize_input(raw):
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>16000:
        raise ValueError('Raw input exceeds terminal input limit')
    text=re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', raw)
    text=re.sub(r'(?:\x1b\[|\^\[\[)[0-?]*[ -/]*[@-~]', '', text)
    text=re.sub(r'\x1b[ -/]*[@-~]', '', text)
    text=''.join(c for c in text if c in '\n\t' or ord(c)>=32 and ord(c)!=127)
    return text, {'normalized':text!=raw,'removed_character_count':len(raw)-len(text),
                  'raw_retained':False,'policy':'terminal-controls-v1'}
