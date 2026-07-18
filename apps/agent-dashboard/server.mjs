import { createServer } from 'node:http';
import { readFile, readdir, realpath, stat } from 'node:fs/promises';
import { dirname, extname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../..');
const ORCHESTRATION = join(ROOT, 'orchestration');
const PUBLIC = join(__dirname, 'public');
const MAX_JSON_BYTES = 1_000_000;
const MAX_FILES = 100;

const MIME = Object.freeze({
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
});

const COMMON_HEADERS = Object.freeze({
  'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
  'Referrer-Policy': 'no-referrer'
});

export async function readJSONSafe(filePath, source = 'unknown') {
  try {
    const info = await stat(filePath);
    if (info.size > MAX_JSON_BYTES) return { data: null, error: safeError(source, 'file_too_large') };
    const value = JSON.parse(await readFile(filePath, 'utf8'));
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return { data: null, error: safeError(source, 'invalid_shape') };
    }
    return { data: value, error: null };
  } catch (error) {
    if (error.code === 'ENOENT') return { data: null, error: safeError(source, 'missing') };
    if (error instanceof SyntaxError) return { data: null, error: safeError(source, 'corrupt_json') };
    return { data: null, error: safeError(source, 'read_error') };
  }
}

async function readJSONDirectory(dirPath, source) {
  try {
    const entries = (await readdir(dirPath)).filter((name) => name.endsWith('.json')).sort().slice(0, MAX_FILES);
    const records = [];
    const errors = [];
    for (const file of entries) {
      const result = await readJSONSafe(join(dirPath, file), source);
      if (result.data) records.push({ file, data: result.data });
      if (result.error) errors.push({ ...result.error, file });
    }
    return { records, errors };
  } catch (error) {
    if (error.code === 'ENOENT') return { records: [], errors: [] };
    return { records: [], errors: [safeError(source, 'directory_read_error')] };
  }
}

async function readResultMetadata(dirPath) {
  try {
    const entries = (await readdir(dirPath)).filter((name) => name.endsWith('.md')).sort().slice(0, MAX_FILES);
    const records = [];
    for (const file of entries) {
      try {
        const info = await stat(join(dirPath, file));
        records.push({ file, sizeBytes: info.size });
      } catch {
        records.push({ file, error: 'read_error' });
      }
    }
    return { records, errors: [] };
  } catch (error) {
    if (error.code === 'ENOENT') return { records: [], errors: [] };
    return { records: [], errors: [safeError('results', 'directory_read_error')] };
  }
}

export async function buildStatus(orchestrationDir = ORCHESTRATION) {
  const errors = [];
  const projectFile = await readJSONSafe(join(orchestrationDir, 'project-status.json'), 'project');
  const agentsFile = await readJSONSafe(join(orchestrationDir, 'agents.json'), 'agents');
  if (projectFile.error) errors.push(projectFile.error);
  if (agentsFile.error) errors.push(agentsFile.error);

  const [contracts, drafts, runtimes, results, environment] = await Promise.all([
    readJSONDirectory(join(orchestrationDir, 'tasks'), 'tasks'),
    readJSONDirectory(join(orchestrationDir, 'drafts'), 'drafts'),
    readJSONDirectory(join(orchestrationDir, 'runtime', 'tasks'), 'runtime'),
    readResultMetadata(join(orchestrationDir, 'results')),
    readJSONSafe(join(orchestrationDir, 'environment-lock.json'), 'environment')
  ]);
  errors.push(...contracts.errors, ...drafts.errors, ...runtimes.errors, ...results.errors);
  if (environment.error) errors.push(environment.error);

  const runtimeById = new Map(runtimes.records.map(({ data }) => [text(data.taskId), projectRuntime(data)]));
  const resultByTask = new Map(results.records.map((item) => [item.file.replace(/\.md$/i, ''), item]));
  const tasks = [];
  const taskIds = new Set();
  for (const { file, data } of contracts.records) {
    const id = text(data.id) || file.replace(/\.json$/i, '');
    if (taskIds.has(id)) continue;
    taskIds.add(id);
    tasks.push(projectTask(data, 'contract', runtimeById.get(id), resultByTask.get(id)));
    runtimeById.delete(id);
  }
  for (const { file, data } of drafts.records) {
    const id = text(data.id) || file.replace(/\.json$/i, '');
    if (taskIds.has(id)) continue;
    taskIds.add(id);
    tasks.push(projectTask(data, 'draft', runtimeById.get(id), resultByTask.get(id)));
    runtimeById.delete(id);
  }
  for (const [id, runtime] of runtimeById) tasks.push({ id, kind: 'runtime-only', runtime });

  return {
    project: projectFile.data ? projectProject(projectFile.data) : null,
    agents: agentsFile.data ? projectAgents(agentsFile.data) : { agents: [] },
    tasks,
    environmentGate: environment.data ? projectEnvironment(environment.data) : null,
    results: results.records,
    errors,
    lastUpdated: new Date().toISOString()
  };
}

function projectProject(value) {
  return compact({
    project: text(value.project), phase: text(value.phase), summary: text(value.summary), updatedAt: text(value.updatedAt),
    milestones: array(value.milestones).map((item) => compact({ id: text(item?.id), name: text(item?.name), status: text(item?.status) }))
  });
}

function projectAgents(value) {
  return { agents: array(value.agents).map((item) => compact({ id: text(item?.id), name: text(item?.name), role: text(item?.role), status: text(item?.status) })) };
}

function projectTask(value, kind, runtime, result) {
  const budget = value.budget && typeof value.budget === 'object' ? compact({
    class: text(value.budget.class), maxRuntimeMinutes: number(value.budget.maxRuntimeMinutes),
    maxInputTokens: number(value.budget.maxInputTokens), maxOutputTokens: number(value.budget.maxOutputTokens),
    maxCost: number(value.budget.maxCost), currency: text(value.budget.currency), maxCorrectionCycles: number(value.budget.maxCorrectionCycles)
  }) : null;
  return compact({
    id: text(value.id), title: text(value.title), kind, lifecycle: text(value.lifecycle), riskLevel: text(value.riskLevel),
    authority: text(value.authority), requestedBy: text(value.requestedBy), executor: text(value.executor), model: text(value.model),
    complexity: text(value.complexity),
    modelPolicy: value.modelPolicy && typeof value.modelPolicy === 'object' ? compact({
      version: number(value.modelPolicy.version), selectedBy: text(value.modelPolicy.selectedBy), defaultApplied: Boolean(value.modelPolicy.defaultApplied)
    }) : null,
    approval: value.approval && typeof value.approval === 'object' ? compact({ status: text(value.approval.status), approvedBy: text(value.approval.approvedBy), approvedAt: text(value.approval.approvedAt) }) : null,
    budget, runtime, result: result ? { available: true, sizeBytes: result.sizeBytes ?? null } : { available: false }
  });
}

function projectRuntime(value) {
  const usage = value.usage && typeof value.usage === 'object' ? compact({ inputTokens: number(value.usage.inputTokens), outputTokens: number(value.usage.outputTokens), cost: number(value.usage.cost) }) : null;
  return compact({
    status: text(value.status), owner: text(value.owner), usage, correctionCycles: number(value.correctionCycles),
    createdAt: text(value.createdAt), updatedAt: text(value.updatedAt), startedAt: text(value.startedAt), completedAt: text(value.completedAt),
    estimatedInputTokens: number(value.estimatedInputTokens), budgetReason: text(value.budgetReason),
    environment: value.environment && typeof value.environment === 'object' ? { ok: Boolean(value.environment.ok), issues: array(value.environment.issues).map(text).filter(Boolean) } : null,
    verification: value.verification && typeof value.verification === 'object' ? { ok: Boolean(value.verification.ok) } : null,
    nextActions: array(value.nextActions).map(text).filter(Boolean)
  });
}

function projectEnvironment(value) {
  return compact({
    platform: text(value.platform), arch: text(value.arch), node: text(value.node), opencodeCli: text(value.opencodeCli),
    jujutsu: text(value.jujutsu), provider: text(value.provider), models: array(value.models).map(text).filter(Boolean),
    taskSchemaVersion: number(value.taskSchemaVersion), supervisorSchemaVersion: number(value.supervisorSchemaVersion)
  });
}

export function createApp(orchestrationDir = ORCHESTRATION, publicDir = PUBLIC) {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
      if (req.method !== 'GET') return sendJSON(res, 405, { error: 'method_not_allowed' }, { Allow: 'GET' });
      if (url.pathname === '/api/status') return sendJSON(res, 200, await buildStatus(orchestrationDir), { 'Cache-Control': 'no-store' });

      const candidate = await resolveStaticPath(publicDir, url.pathname === '/' ? '/index.html' : url.pathname);
      if (!candidate) return sendText(res, 403, 'Forbidden');
      try {
        const content = await readFile(candidate);
        res.writeHead(200, { ...COMMON_HEADERS, 'Content-Type': MIME[extname(candidate)] || 'application/octet-stream' });
        res.end(content);
      } catch (error) {
        sendText(res, error.code === 'ENOENT' ? 404 : 500, error.code === 'ENOENT' ? 'Not Found' : 'Server Error');
      }
    } catch {
      sendJSON(res, 500, { error: 'internal_error' });
    }
  });
}

async function resolveStaticPath(publicDir, pathname) {
  let decoded;
  try { decoded = decodeURIComponent(pathname); } catch { return null; }
  if (decoded.includes('\u0000') || decoded.includes('\\')) return null;
  const root = resolve(publicDir);
  const candidate = resolve(root, `.${decoded}`);
  if (!isWithin(root, candidate)) return null;
  try {
    const [realRoot, realCandidate] = await Promise.all([realpath(root), realpath(candidate)]);
    if (!isWithin(realRoot, realCandidate)) return null;
    return realCandidate;
  } catch (error) {
    return error.code === 'ENOENT' ? candidate : null;
  }
}

function isWithin(root, candidate) {
  const rel = relative(root, candidate);
  return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel));
}

function sendJSON(res, status, value, extra = {}) {
  res.writeHead(status, { ...COMMON_HEADERS, 'Content-Type': 'application/json; charset=utf-8', ...extra });
  res.end(JSON.stringify(value));
}

function sendText(res, status, value) {
  res.writeHead(status, { ...COMMON_HEADERS, 'Content-Type': 'text/plain; charset=utf-8' });
  res.end(value);
}

function safeError(source, code) { return { source, code }; }
function array(value) { return Array.isArray(value) ? value : []; }
function text(value) { return typeof value === 'string' ? value.slice(0, 1000) : null; }
function number(value) { return typeof value === 'number' && Number.isFinite(value) ? value : null; }
function compact(value) { return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== null && item !== undefined)); }

const appPath = process.argv[1] ? resolve(process.argv[1]) : '';
if (appPath === fileURLToPath(import.meta.url)) {
  createApp().listen(4174, '127.0.0.1', () => console.log('Agent dashboard running at http://127.0.0.1:4174'));
}
