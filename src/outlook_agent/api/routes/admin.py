"""Admin dashboard — served at /admin, with process status and reload helpers."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["admin"])

_LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
_API_LABEL = "com.personal.outlook-agent.api"
_SYNC_LABEL = "com.personal.outlook-agent.sync"
_API_PLIST = _LAUNCH_AGENTS / f"{_API_LABEL}.plist"
_SYNC_PLIST = _LAUNCH_AGENTS / f"{_SYNC_LABEL}.plist"


def _pgrep(pattern: str) -> str | None:
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    return r.stdout.strip().split("\n")[0] if r.returncode == 0 else None


def _launchctl_loaded(label: str) -> bool:
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    return label in r.stdout


def _reload_plist(label: str, plist: Path) -> str:
    if not plist.exists():
        return "plist_not_found"
    check = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    if label in check.stdout:
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    r = subprocess.run(["launchctl", "load", str(plist)], capture_output=True)
    return "ok" if r.returncode == 0 else f"error (exit {r.returncode})"


@router.get("/api/v1/admin/process_status")
async def process_status() -> JSONResponse:
    """Return process and launchd service status."""
    loop = asyncio.get_event_loop()
    mcp_pid, api_pid, api_loaded, sync_loaded = await asyncio.gather(
        loop.run_in_executor(None, _pgrep, "outlook-agent-mcp"),
        loop.run_in_executor(None, _pgrep, "outlook-agent-api"),
        loop.run_in_executor(None, _launchctl_loaded, _API_LABEL),
        loop.run_in_executor(None, _launchctl_loaded, _SYNC_LABEL),
    )
    return JSONResponse({
        "mcp": {"running": mcp_pid is not None, "pid": mcp_pid},
        "api": {"running": api_pid is not None, "pid": api_pid},
        "launchd_api": {"loaded": api_loaded, "plist_exists": _API_PLIST.exists()},
        "launchd_sync": {"loaded": sync_loaded, "plist_exists": _SYNC_PLIST.exists()},
    })


@router.post("/api/v1/admin/reload")
async def reload_services() -> JSONResponse:
    """Restart any installed launchd services."""
    loop = asyncio.get_event_loop()
    api_r, sync_r = await asyncio.gather(
        loop.run_in_executor(None, _reload_plist, _API_LABEL, _API_PLIST),
        loop.run_in_executor(None, _reload_plist, _SYNC_LABEL, _SYNC_PLIST),
    )
    return JSONResponse({"api": api_r, "sync": sync_r})


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outlook Agent Admin</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;background:#f0f2f5;color:#1a1a2e;min-height:100vh}

/* ── top bar ── */
.topbar{background:#1a1a2e;color:#fff;padding:0 24px;height:52px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.topbar-logo{font-weight:700;font-size:15px;letter-spacing:.4px}
.topbar-logo span{color:#4dabf7}
.topbar-status{display:flex;align-items:center;gap:6px;font-size:12px;color:#adb5bd}
.spacer{flex:1}
.topbar-time{font-size:12px;color:#868e96}

/* ── buttons ── */
.btn{padding:6px 14px;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer;border:none;transition:opacity .1s}
.btn:hover{opacity:.85} .btn:active{opacity:.7} .btn:disabled{opacity:.5;cursor:not-allowed}
.btn-sm{padding:4px 10px;font-size:12px}
.btn-ghost{background:rgba(255,255,255,.12);color:#fff}
.btn-outline{background:transparent;border:1px solid #dee2e6;color:#495057}

/* ── tabs ── */
.tabs{background:#fff;border-bottom:1px solid #e9ecef;padding:0 24px;display:flex}
.tab{padding:12px 18px;font-size:13px;font-weight:500;cursor:pointer;color:#868e96;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;white-space:nowrap}
.tab:hover{color:#4dabf7}
.tab.active{color:#4dabf7;border-bottom-color:#4dabf7}

/* ── content ── */
.content{padding:24px;max-width:1100px;margin:0 auto}
.section{display:none} .section.active{display:block}

/* ── grid / cards ── */
.grid{display:grid;gap:16px}
.grid-2{grid-template-columns:1fr 1fr}
@media(max-width:720px){.grid-2{grid-template-columns:1fr}}
.card{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.06),0 1px 8px rgba(0,0,0,.03)}
.card-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:#868e96;margin-bottom:14px}

/* ── status rows ── */
.srow{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f3f5}
.srow:last-child{border-bottom:none}
.srow-label{display:flex;align-items:center;gap:8px;font-size:13px;color:#495057}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;display:inline-block}
.dot-ok{background:#51cf66} .dot-fail{background:#ff6b6b} .dot-warn{background:#ffd43b} .dot-muted{background:#ced4da}

/* ── badges ── */
.badge{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600}
.badge-ok{background:#d3f9d8;color:#2f9e44}
.badge-fail{background:#ffe3e3;color:#c92a2a}
.badge-warn{background:#fff3bf;color:#e67700}
.badge-muted{background:#f1f3f5;color:#868e96}
.badge-blue{background:#dbe4ff;color:#3b5bdb}

/* ── capability grid ── */
.cap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:10px}
.cap-item{display:flex;align-items:center;gap:8px;padding:10px 12px;background:#f8f9fa;border-radius:8px;font-size:12px;font-family:'SF Mono','Fira Code',monospace}

/* ── table ── */
.overflow-x{overflow-x:auto}
.dtable{width:100%;border-collapse:collapse;font-size:13px}
.dtable th{text-align:left;padding:8px 12px;background:#f8f9fa;color:#868e96;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.6px}
.dtable td{padding:10px 12px;border-bottom:1px solid #f1f3f5;vertical-align:top}
.dtable tr:last-child td{border-bottom:none}
.dtable tbody tr:hover td{background:#f8f9fa}
.draft-subject{font-weight:500;color:#1a1a2e}
.draft-preview{font-size:12px;color:#868e96;margin-top:2px;max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mono{font-family:'SF Mono','Fira Code',monospace}

/* ── misc ── */
.loading{color:#adb5bd;font-style:italic;padding:12px 0;font-size:13px}
.err{color:#c92a2a;font-size:13px;padding:8px 0}
.row-actions{display:flex;align-items:center;gap:10px;margin-top:14px}
.toast{font-size:12px;padding:5px 10px;border-radius:6px;display:none}
.toast-ok{background:#d3f9d8;color:#2f9e44}
.toast-err{background:#ffe3e3;color:#c92a2a}
.section-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.section-hdr .card-title{margin-bottom:0}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-logo">Outlook <span>Agent</span></div>
  <div class="topbar-status">
    <span class="dot dot-muted" id="g-dot"></span>
    <span id="g-status">Loading…</span>
  </div>
  <div class="spacer"></div>
  <div class="topbar-time" id="g-time"></div>
  <button class="btn btn-ghost btn-sm" onclick="refresh()">↻ Refresh</button>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('overview',this)">Overview</div>
  <div class="tab" onclick="switchTab('capabilities',this)">Capabilities</div>
  <div class="tab" onclick="switchTab('accounts',this)">Accounts</div>
  <div class="tab" onclick="switchTab('drafts',this)">Drafts</div>
</div>

<div class="content">

  <!-- OVERVIEW -->
  <div class="section active" id="sec-overview">
    <div class="grid grid-2" style="margin-bottom:16px">

      <div class="card">
        <div class="card-title">Outlook Health</div>
        <div id="health-rows"><div class="loading">Loading…</div></div>
      </div>

      <div class="card">
        <div class="card-title">Processes &amp; Services</div>
        <div id="proc-rows"><div class="loading">Loading…</div></div>
        <div class="row-actions">
          <button class="btn btn-outline btn-sm" id="reload-btn" onclick="reloadSvc()">↺ Reload Services</button>
          <span class="toast" id="reload-toast"></span>
        </div>
      </div>

    </div>

    <div class="card">
      <div class="card-title">Diagnostic Checks</div>
      <div id="check-rows"><div class="loading">Loading…</div></div>
    </div>
  </div>

  <!-- CAPABILITIES -->
  <div class="section" id="sec-capabilities">
    <div class="card">
      <div class="card-title">Provider Capabilities</div>
      <div class="cap-grid" id="cap-grid"><div class="loading">Loading…</div></div>
    </div>
  </div>

  <!-- ACCOUNTS -->
  <div class="section" id="sec-accounts">
    <div class="card">
      <div class="section-hdr">
        <div class="card-title">Accounts</div>
      </div>
      <div id="acct-content"><div class="loading">Loading…</div></div>
    </div>
  </div>

  <!-- DRAFTS -->
  <div class="section" id="sec-drafts">
    <div class="card">
      <div class="section-hdr">
        <div class="card-title">Drafts</div>
        <button class="btn btn-outline btn-sm" onclick="loadDrafts()">↻ Reload</button>
      </div>
      <div id="draft-content"><div class="loading">Loading…</div></div>
    </div>
  </div>

</div>

<script>
'use strict';

// ── helpers ────────────────────────────────────────────────────────────────

function mkDot(ok) {
  return `<span class="dot ${ok ? 'dot-ok' : 'dot-fail'}"></span>`;
}

function mkBadge(ok, t, f) {
  return ok
    ? `<span class="badge badge-ok">✓ ${t||'OK'}</span>`
    : `<span class="badge badge-fail">✗ ${f||'FAIL'}</span>`;
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`HTTP ${r.status} ${r.statusText}`);
  return r.json();
}

// ── tabs ───────────────────────────────────────────────────────────────────

function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('sec-' + name).classList.add('active');
}

// ── diagnostics ────────────────────────────────────────────────────────────

async function loadDiagnostics() {
  try {
    const d = await api('/api/v1/diagnostics');
    const ok = d.checks.every(c => c.ok);
    const dotEl = document.getElementById('g-dot');
    dotEl.className = 'dot ' + (ok ? 'dot-ok' : 'dot-fail');
    document.getElementById('g-status').textContent = ok ? 'Healthy' : 'Issues detected';

    const o = d.outlook || {}, p = d.permissions || {};
    document.getElementById('health-rows').innerHTML = `
      <div class="srow">
        <span class="srow-label">${mkDot(o.running)} Outlook running</span>
        ${mkBadge(o.running)}
      </div>
      <div class="srow">
        <span class="srow-label">${mkDot(o.mode==='classic')} Mode</span>
        <span class="badge ${o.mode==='classic'?'badge-ok':'badge-fail'}">${esc(o.mode||'—')}</span>
      </div>
      <div class="srow">
        <span class="srow-label"><span class="dot dot-muted"></span> Version</span>
        <span class="mono" style="font-size:12px">${esc(o.version||'—')}</span>
      </div>
      <div class="srow">
        <span class="srow-label">${mkDot(p.automation)} Automation permission</span>
        ${mkBadge(p.automation)}
      </div>`;

    document.getElementById('check-rows').innerHTML = d.checks.map(c => `
      <div class="srow">
        <span class="srow-label">${mkDot(c.ok)} ${esc(c.name)}</span>
        <div style="display:flex;align-items:center;gap:6px">
          ${c.detail ? `<span class="badge badge-muted">${esc(c.detail)}</span>` : ''}
          ${mkBadge(c.ok)}
          ${c.remediation ? `<span class="badge badge-warn" title="${esc(c.remediation)}">! hint</span>` : ''}
        </div>
      </div>`).join('');

    const caps = d.capabilities || {};
    document.getElementById('cap-grid').innerHTML =
      Object.entries(caps).map(([k, v]) =>
        `<div class="cap-item">${mkDot(v)}<span>${esc(k)}</span></div>`
      ).join('') || '<div class="loading">No capabilities</div>';

  } catch(e) {
    document.getElementById('health-rows').innerHTML = `<div class="err">Failed: ${esc(e.message)}</div>`;
    document.getElementById('g-dot').className = 'dot dot-fail';
    document.getElementById('g-status').textContent = 'Error';
  }
}

// ── process status ─────────────────────────────────────────────────────────

async function loadProcessStatus() {
  try {
    const d = await api('/api/v1/admin/process_status');
    const pidBadge = (pid) => pid ? `<span class="badge badge-muted mono">pid ${pid}</span>` : '';
    const plistBadge = (exists) => exists
      ? '<span class="badge badge-muted">plist found</span>'
      : '<span class="badge badge-warn">no plist</span>';

    document.getElementById('proc-rows').innerHTML = `
      <div class="srow">
        <span class="srow-label">${mkDot(d.mcp.running)} MCP server</span>
        <div style="display:flex;gap:5px">
          ${d.mcp.running ? `<span class="badge badge-ok">running</span>${pidBadge(d.mcp.pid)}` : '<span class="badge badge-muted">stopped (Claude Desktop manages)</span>'}
        </div>
      </div>
      <div class="srow">
        <span class="srow-label">${mkDot(d.api.running)} REST API</span>
        <div style="display:flex;gap:5px">
          ${d.api.running ? `<span class="badge badge-ok">running</span>${pidBadge(d.api.pid)}` : '<span class="badge badge-muted">stopped</span>'}
        </div>
      </div>
      <div class="srow">
        <span class="srow-label">${mkDot(d.launchd_api.loaded)} launchd — api</span>
        <div style="display:flex;gap:5px">
          ${mkBadge(d.launchd_api.loaded, 'loaded', 'not loaded')}
          ${plistBadge(d.launchd_api.plist_exists)}
        </div>
      </div>
      <div class="srow">
        <span class="srow-label">${mkDot(d.launchd_sync.loaded)} launchd — sync</span>
        <div style="display:flex;gap:5px">
          ${mkBadge(d.launchd_sync.loaded, 'loaded', 'not loaded')}
          ${plistBadge(d.launchd_sync.plist_exists)}
        </div>
      </div>`;
  } catch(e) {
    document.getElementById('proc-rows').innerHTML = `<div class="err">Failed: ${esc(e.message)}</div>`;
  }
}

// ── reload ─────────────────────────────────────────────────────────────────

async function reloadSvc() {
  const btn = document.getElementById('reload-btn');
  const toast = document.getElementById('reload-toast');
  btn.disabled = true; btn.textContent = 'Reloading…';
  toast.style.display = 'none';
  try {
    const d = await api('/api/v1/admin/reload', {method:'POST'});
    const msg = Object.entries(d).map(([k,v]) => `${k}: ${v}`).join(' · ');
    toast.textContent = msg;
    toast.className = 'toast toast-ok';
    toast.style.display = 'inline-block';
    setTimeout(loadProcessStatus, 1200);
  } catch(e) {
    toast.textContent = 'Error: ' + e.message;
    toast.className = 'toast toast-err';
    toast.style.display = 'inline-block';
  }
  btn.disabled = false; btn.textContent = '↺ Reload Services';
}

// ── accounts ───────────────────────────────────────────────────────────────

let _accounts = [];

async function loadAccounts() {
  try {
    _accounts = await api('/api/v1/accounts');
    if (!_accounts.length) {
      document.getElementById('acct-content').innerHTML = '<div class="loading">No accounts found</div>';
      return;
    }
    document.getElementById('acct-content').innerHTML = `
      <div class="overflow-x">
      <table class="dtable">
        <thead><tr><th>ID</th><th>Name</th><th>Email</th></tr></thead>
        <tbody>${_accounts.map(a => `
          <tr>
            <td><span class="mono">${esc(a.account_id)}</span></td>
            <td>${esc(a.name||'—')}</td>
            <td>${esc(a.email_address||'—')}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      </div>`;
  } catch(e) {
    document.getElementById('acct-content').innerHTML = `<div class="err">Failed: ${esc(e.message)}</div>`;
  }
}

// ── drafts ─────────────────────────────────────────────────────────────────

async function loadDrafts() {
  const el = document.getElementById('draft-content');
  el.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const acctId = _accounts.length ? _accounts[0].account_id : '1';
    const drafts = await api(`/api/v1/drafts?account_id=${encodeURIComponent(acctId)}&limit=30`);
    if (!drafts.length) {
      el.innerHTML = '<div class="loading">No drafts</div>';
      return;
    }
    el.innerHTML = `
      <div class="overflow-x">
      <table class="dtable">
        <thead><tr><th>ID</th><th>Subject / Preview</th><th>Flags</th></tr></thead>
        <tbody>${drafts.map(d => `
          <tr>
            <td><span class="mono">${esc(d.draft_id)}</span></td>
            <td>
              <div class="draft-subject">${esc(d.subject||'(no subject)')}</div>
              <div class="draft-preview">${esc((d.body_text||'').substring(0,130))}</div>
            </td>
            <td>${d.has_original_email ? '<span class="badge badge-blue">original email</span>' : ''}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      </div>`;
  } catch(e) {
    el.innerHTML = `<div class="err">Failed: ${esc(e.message)}</div>`;
  }
}

// ── main ───────────────────────────────────────────────────────────────────

async function refresh() {
  await Promise.all([
    loadDiagnostics(),
    loadProcessStatus(),
    loadAccounts().then(loadDrafts),
  ]);
  document.getElementById('g-time').textContent =
    'Refreshed ' + new Date().toLocaleTimeString();
}

refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard() -> str:
    """Serve the admin dashboard."""
    return _HTML
