"""Read the operator-verified hosted anti-rollback floor; never lower it."""
import argparse
import json
import os
from pathlib import Path
import re

POLICY = Path(__file__).resolve().parents[1] / 'config/hosted-release-policy.json'

def minimum_epoch(requested=None, policy=POLICY):
    value=json.loads(Path(policy).read_text(encoding='utf-8'))
    if (not isinstance(value,dict) or type(value.get('schema')) is not int or value['schema']!=1 or
            type(value.get('minimum_launch_epoch')) is not int or not 0<value['minimum_launch_epoch']<2**64):
        raise ValueError('Hosted release policy is invalid')
    floor=value['minimum_launch_epoch']
    if requested not in (None,'',0,'0'):
        text=str(requested)
        if not re.fullmatch('[1-9][0-9]{0,19}',text) or not floor<=int(text)<2**64:
            raise ValueError('Requested epoch is malformed or below the verified release floor')
        floor=int(text)
    return floor

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requested',default='')
    args=parser.parse_args()
    try:value=minimum_epoch(args.requested)
    except (ValueError,OSError):
        print('::error::Hosted anti-rollback policy rejected; no installed state was invented')
        return 1
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:out.write('minimum_epoch='+str(value)+'\n')
    print('[RELEASE/POLICY][OK] operator-verified minimum launch epoch admitted')
    return 0
if __name__=='__main__':raise SystemExit(main())
