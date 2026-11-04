"""Read-only development capture. Raw profiles/answers never reach output files."""
import argparse
import json
import os
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commons_game.ecosystem_import import sibling_client
from commons_game.montreal_capture import capture_montreal


def main():
    parser = argparse.ArgumentParser(description='Capture the approved Montréal participant scope, read-only')
    parser.add_argument('--protocol-project',type=Path,default=ROOT.parent/'app_protocol_hack')
    parser.add_argument('--scope',type=Path,default=ROOT/'config/montreal-scope.json')
    parser.add_argument('--output',type=Path,required=True,help='New private directory outside the repository')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Private captures must be outside the public repository')
    secrets_path = args.protocol_project/'.streamlit/secrets.toml'
    configured = tomllib.loads(secrets_path.read_text()).get('notion',{}) if secrets_path.exists() else {}
    token = (os.getenv('PROTOHACK_NOTION_TOKEN') or configured.get('protohack_token') or configured.get('api_key')
             or configured.get('token') or os.getenv('NOTION_TOKEN'))
    if not token:
        raise ValueError('Use the existing Notion environment or sibling secret configuration')
    scope = json.loads(args.scope.read_text())
    snapshot,report = capture_montreal(sibling_client(args.protocol_project,token),scope)
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    for name,value in [('ecosystem-snapshot.json',snapshot),('coverage-report.json',report)]:
        path = output/name
        with path.open('x') as target:
            json.dump(value,target,ensure_ascii=False,indent=2)
        path.chmod(0o600)
    print(json.dumps({k:report[k] for k in ('source_records_inspected','person_source_records','response_source_records',
        'scoped_response_records','submitted_inventories','eligible_people','source_local_organisation_mentions',
        'capacities','needs','repeated_submitted_inventories','skipped','missing_fields')},indent=2))
    print('Unresolved identity records:',len(report['unresolved_identity_records']))
    print('Private output:',output)


if __name__=='__main__':
    main()
