"""Apply Desk: private application preparation and optional T3 drafting."""
import argparse
import json
from pathlib import Path
import sys
from .workspace import Workspace


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, help='Dedicated private folder for one member')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='Confirm a profile JSON and snapshot a resume PDF')
    init.add_argument('--profile', required=True)
    init.add_argument('--resume', required=True)
    jobs = sub.add_parser('import-jobs')
    jobs.add_argument('csv')
    sub.add_parser('jobs')
    context = sub.add_parser('context')
    context.add_argument('role_id')
    sub.add_parser('proposals')
    accept = sub.add_parser('accept', help='Member confirms the exact proposal shown by proposals')
    accept.add_argument('proposal_id')
    accept.add_argument('--confirm', required=True, choices=['this-answer'])
    export = sub.add_parser('export-batch')
    export.add_argument('destination', help='New private folder; existing output is never overwritten')
    sub.add_parser('install-browser', help='Install the member-owned browser connection')
    sub.add_parser('setup-t3', help='Create and open a dedicated T3 application project')
    sub.add_parser('mcp', help='Run optional local stdio MCP connector')
    ui = sub.add_parser('serve', help='Open the member interface on this computer')
    ui.add_argument('--port', type=int, default=0)
    ui.add_argument('--no-open', action='store_true')
    sub.add_parser('connection', help='Print MCP command configuration without changing T3 settings')
    args = parser.parse_args(argv)
    try:
        if args.command == 'serve':
            from .web_server import run
            run(args.workspace, args.port, not args.no_open)
            return
        if args.command == 'init':
            workspace = Workspace.create(args.workspace,
                json.loads(Path(args.profile).read_text(encoding='utf-8')), args.resume)
            result = {'workspace': str(workspace.root), 'status': 'initialized'}
        else:
            workspace = Workspace(args.workspace)
            if args.command == 'mcp':
                from .mcp_server import run
                run(workspace.root)
                return
            if args.command == 'install-browser':
                from .integration import install_browser
                result = install_browser(workspace.root)
            elif args.command == 'setup-t3':
                from .mac_actions import t3_setup
                result = t3_setup(workspace.root)
            elif args.command == 'connection':
                from .integration import connection
                result = {'mcpServers': {'apply-desk': connection(workspace.root)}}
            elif args.command == 'import-jobs':
                result = workspace.import_jobs(Path(args.csv).read_text(encoding='utf-8-sig'))
            elif args.command == 'jobs':
                result = workspace.list_jobs()
            elif args.command == 'context':
                result = workspace.context(args.role_id)
            elif args.command == 'proposals':
                result = workspace.proposals()
            elif args.command == 'accept':
                result = workspace.accept(args.proposal_id)
            else:
                result = workspace.export_batch(args.destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
