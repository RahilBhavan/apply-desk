"""Actual SDK client/server stdio subprocess, not mocked tool functions."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from apply_desk.workspace import Workspace


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Run with the optional T3 extra installed')
class MCPTests(unittest.TestCase):
    def test_member_connector_over_stdio(self):
        asyncio.run(self.exercise())

    async def exercise(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resume = root / 'resume.pdf'
            resume.write_bytes(b'%PDF-1.4\nfictional')
            member = Workspace.create(root / 'member', {'major': 'Computer Science'}, resume)
            member.import_jobs('company,title,apply_url\nExample,Intern,https://jobs.example.com/1\n')
            role = member.list_jobs()['jobs'][0]['id']
            parameters = StdioServerParameters(command=sys.executable, args=[
                '-m', 'apply_desk', '--workspace', str(member.root), 'mcp'])
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    tools = await client.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertEqual(len(names), 5)
                    self.assertFalse(any('accept' in name or 'submit' in name for name in names))
                    jobs = await client.call_tool('list_apply_jobs', {})
                    self.assertFalse(jobs.isError)
                    revision = member.list_jobs()['revision']
                    captured = await client.call_tool('capture_application_questions', {
                        'role_id': role, 'expected_revision': revision, 'questions': [
                            {'label': 'Why this role?', 'type': 'textarea', 'options': [], 'required': True}]})
                    self.assertFalse(captured.isError)
                    context = await client.call_tool('get_application_context', {'role_id': role})
                    self.assertIn('Computer Science', str(context))
                    result = await client.call_tool('propose_application_answer', {
                        'role_id': role, 'label': 'Why this role?', 'answer': 'To use my Computer Science studies.',
                        'evidence_keys': ['profile:major'], 'expected_revision': member.context(role)['revision']})
                    self.assertFalse(result.isError)
                    self.assertEqual(member.context(role)['fields'][0]['answer'], '')
                    forbidden = await client.call_tool('submit_application', {'role_id': role})
                    self.assertTrue(forbidden.isError)
            # A new server process reads the same persisted proposal.
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    result = await client.call_tool('list_answer_proposals', {})
                    self.assertIn('To use my Computer Science studies.', str(result))
                    self.assertEqual(len(member.proposals()['proposals']), 1)


if __name__ == '__main__':
    unittest.main()
