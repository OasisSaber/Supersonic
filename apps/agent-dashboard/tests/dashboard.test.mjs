import assert from 'node:assert/strict';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { buildStatus, createApp } from '../server.mjs';

test('buildStatus exposes only explicit dashboard fields and merges runtime', async () => {
  const fixture = await makeFixture();
  await json(path.join(fixture.orchestration, 'project-status.json'), {
    project: 'Cockpit', phase: 'Design', summary: 'Safe', updatedAt: 'now', secret: 'PROJECT_SECRET',
    milestones: [{ id: 'm1', name: 'Workflow', status: 'IN_PROGRESS', token: 'NOPE' }]
  });
  await json(path.join(fixture.orchestration, 'agents.json'), {
    agents: [{ id: 'leader', name: 'Codex', role: 'Leader', status: 'ACTIVE', cookie: 'AGENT_SECRET' }]
  });
  await json(path.join(fixture.orchestration, 'tasks', 'TASK-9.json'), {
    id: 'TASK-9', title: 'Dashboard', lifecycle: 'ACTIVE', riskLevel: 'L1', authority: 'DELEGATABLE',
    requestedBy: 'Oasis', executor: 'opencode', complexity: 'MEDIUM', model: 'deepseek/deepseek-v4-flash',
    modelPolicy: { version: 1, selectedBy: 'codex-contract-approval', defaultApplied: false, internalPrompt: 'POLICY_SECRET' },
    prompt: 'PROMPT_SECRET', approval: { status: 'APPROVED', approvedBy: 'Oasis', contractHash: 'HASH_SECRET' },
    budget: { maxRuntimeMinutes: 20, maxInputTokens: 30000, maxOutputTokens: 8000, maxCost: 0.25, currency: 'USD', maxCorrectionCycles: 1 }
  });
  await json(path.join(fixture.orchestration, 'runtime', 'tasks', 'TASK-9.json'), {
    taskId: 'TASK-9', status: 'AWAITING_USER', owner: 'supervisor', pid: 987654, commandLine: 'PRIVATE_COMMAND',
    usage: { inputTokens: 100, outputTokens: 20, cost: 0.01 }, environment: { ok: true, issues: [], env: 'PRIVATE_ENV' }
  });
  await json(path.join(fixture.orchestration, 'environment-lock.json'), {
    platform: 'win32', arch: 'x64', node: 'v24', opencodeCli: '1.18.2', jujutsu: '0.43.0', provider: 'deepseek', models: ['deepseek/v4'], apiKey: 'KEY_SECRET'
  });
  await writeFile(path.join(fixture.orchestration, 'results', 'TASK-9.md'), '# result\npassword=RESULT_SECRET\n');

  const status = await buildStatus(fixture.orchestration);
  assert.equal(status.tasks[0].authority, 'DELEGATABLE');
  assert.equal(status.tasks[0].budget.maxInputTokens, 30000);
  assert.equal(status.tasks[0].complexity, 'MEDIUM');
  assert.equal(status.tasks[0].model, 'deepseek/deepseek-v4-flash');
  assert.equal(status.tasks[0].modelPolicy.selectedBy, 'codex-contract-approval');
  assert.equal(status.tasks[0].runtime.status, 'AWAITING_USER');
  assert.equal(status.tasks[0].runtime.usage.outputTokens, 20);
  assert.equal(status.tasks[0].result.available, true);
  const serialized = JSON.stringify(status);
  for (const secret of ['PROJECT_SECRET', 'AGENT_SECRET', 'PROMPT_SECRET', 'POLICY_SECRET', 'HASH_SECRET', 'PRIVATE_COMMAND', 'PRIVATE_ENV', 'KEY_SECRET', 'RESULT_SECRET', '987654']) {
    assert.equal(serialized.includes(secret), false, `response leaked ${secret}`);
  }
});

test('corrupt and missing JSON degrade without filesystem details', async () => {
  const fixture = await makeFixture();
  await writeFile(path.join(fixture.orchestration, 'project-status.json'), '{broken');
  await writeFile(path.join(fixture.orchestration, 'tasks', 'bad.json'), '{broken');
  const status = await buildStatus(fixture.orchestration);
  assert.equal(status.project, null);
  assert.ok(status.errors.some((item) => item.source === 'project' && item.code === 'corrupt_json'));
  assert.ok(status.errors.some((item) => item.source === 'tasks' && item.file === 'bad.json'));
  assert.equal(JSON.stringify(status.errors).includes(fixture.root), false);
});

test('formal contracts take precedence over promoted drafts without hiding draft-only tasks', async () => {
  const fixture = await makeFixture();
  await json(path.join(fixture.orchestration, 'tasks', 'TASK-2.json'), {
    id: 'TASK-2', title: 'Formal dashboard task', lifecycle: 'ACTIVE', authority: 'DELEGATABLE'
  });
  await json(path.join(fixture.orchestration, 'drafts', 'TASK-2.json'), {
    id: 'TASK-2', title: 'Promoted duplicate', lifecycle: 'PROMOTED', approval: { status: 'PROMOTED' }
  });
  await json(path.join(fixture.orchestration, 'drafts', 'TASK-3.json'), {
    id: 'TASK-3', title: 'Pending draft only', lifecycle: 'DRAFT', approval: { status: 'PENDING' }
  });
  await json(path.join(fixture.orchestration, 'runtime', 'tasks', 'TASK-2.json'), {
    taskId: 'TASK-2', status: 'INTEGRATED', owner: 'Oasis'
  });

  const status = await buildStatus(fixture.orchestration);
  assert.deepEqual(status.tasks.map((task) => task.id), ['TASK-2', 'TASK-3']);
  assert.equal(status.tasks[0].kind, 'contract');
  assert.equal(status.tasks[0].title, 'Formal dashboard task');
  assert.equal(status.tasks[0].runtime.status, 'INTEGRATED');
  assert.equal(status.tasks[1].kind, 'draft');
  assert.equal(status.tasks[1].title, 'Pending draft only');
  assert.equal(new Set(status.tasks.map((task) => task.id)).size, status.tasks.length);
});

test('HTTP server is read-only and enforces security headers and path boundary', async (t) => {
  const fixture = await makeFixture();
  await json(path.join(fixture.orchestration, 'project-status.json'), { project: 'Cockpit' });
  await json(path.join(fixture.orchestration, 'agents.json'), { agents: [] });
  await json(path.join(fixture.orchestration, 'environment-lock.json'), { platform: 'win32' });
  await writeFile(path.join(fixture.public, 'index.html'), '<!doctype html><title>Dashboard</title>');
  const server = createApp(fixture.orchestration, fixture.public);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const { port } = server.address();

  const api = await fetch(`http://127.0.0.1:${port}/api/status`);
  assert.equal(api.status, 200);
  assert.equal(api.headers.get('cache-control'), 'no-store');
  assert.equal(api.headers.get('x-content-type-options'), 'nosniff');
  assert.match(api.headers.get('content-security-policy'), /default-src 'self'/);
  assert.equal((await api.json()).project.project, 'Cockpit');

  const page = await fetch(`http://127.0.0.1:${port}/`);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /Dashboard/);
  const post = await fetch(`http://127.0.0.1:${port}/api/status`, { method: 'POST' });
  assert.equal(post.status, 405);
  assert.equal(post.headers.get('allow'), 'GET');
  const traversal = await fetch(`http://127.0.0.1:${port}/%5c..%5csecret.txt`);
  assert.equal(traversal.status, 403);
});

async function makeFixture() {
  const root = await mkdtemp(path.join(tmpdir(), 'agent-dashboard-test-'));
  const orchestration = path.join(root, 'orchestration');
  const publicDir = path.join(root, 'public');
  for (const dir of ['tasks', 'drafts', path.join('runtime', 'tasks'), 'results']) await mkdir(path.join(orchestration, dir), { recursive: true });
  await mkdir(publicDir, { recursive: true });
  return { root, orchestration, public: publicDir };
}

async function json(file, value) {
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, `${JSON.stringify(value, null, 2)}\n`);
}
