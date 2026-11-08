'use strict';
/* FinePrint desktop renderer — vanilla JS over window.fineprint (preload).
 * Views: home (feed + definitions), check, wall, settings. */
const $ = (id) => document.getElementById(id);
const fp = window.fineprint;

let status = null;
let selectedAgent = 'codex';

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function showView(name) {
  for (const v of ['home', 'check', 'wall', 'settings']) {
    $(`view-${v}`).classList.toggle('hidden', v !== name);
  }
  for (const b of document.querySelectorAll('.nav-btn')) {
    b.classList.toggle('active', b.dataset.view === name);
  }
  if (name === 'home') renderFeed();
  if (name === 'settings') renderSettings();
}

function verdictHtml(v) {
  return `<div class="verdict ${esc(v.status)}"><h3>${esc(v.title)}</h3><p>${esc(v.detail)}</p></div>`;
}

/** Boundaries under test: which rules fire most, which agents keep
 * testing them. A view on the feed items, not new measurement. */
function summaryHtmlFor(s) {
  if (!s || !s.blocked) return '';
  const rules = (s.byRule || []).map((r) => `${esc(r.ruleId || r.rule || 'unknown')} ×${r.count}`).join(', ');
  const agents = (s.byAgent || []).length
    ? ` · by agent: ${(s.byAgent || []).map((a) => `${esc(a.agent)} ×${a.count}`).join(', ')}`
    : ' · no agent recorded';
  return `<div class="feed-summary"><p><strong>Boundaries under test:</strong> ${s.blocked} blocked attempt${s.blocked === 1 ? '' : 's'}${rules ? ` · ${rules}` : ''}${agents}</p></div>`;
}

function renderFeed() {
  Promise.all([fp.feed(), fp.feedSummary()]).then(([items, summary]) => {
    const list = $('feedList');
    if (!items.length) {
      list.innerHTML = '<p class="muted">Nothing yet — run a check or run your agent inside the wall.</p>';
      return;
    }
    list.innerHTML = summaryHtmlFor(summary) + items.map((it) => {
      const when = it.ts ? new Date(it.ts).toLocaleString() : '';
      const rule = it.rule ? `<p class="rule">Stopped by: ${esc(it.rule)}${it.catalogue && it.catalogue.length ? ` (${esc(it.catalogue.join(', '))})` : ''}</p>` : '';
      const det = it.determinismLine ? `<p class="determinism">${esc(it.determinismLine)}</p>` : '';
      const detail = it.detail ? `<p>${esc(it.detail)}</p>` : '';
      return `<div class="feed-item ${esc(it.kind)}"><time>${esc(when)}</time><p><strong>${esc(it.title)}</strong></p>${rule}${det}${detail}</div>`;
    }).join('');
  });
}

function renderStatus() {
  return fp.status().then((s) => {
    status = s;
    $('protectionLine').textContent = s.protectionLine;
    const d = s.definitions;
    if (d.version) {
      $('definitionsStatus').textContent = d.valid
        ? `Definitions v${d.version} (${d.source}) — ${d.ruleCount} rules, up to date as of ${d.version}.`
        : `Definitions — could not verify: ${d.validReason}`;
      $('definitionsNote').textContent = d.families.map((f) => f.name).join(' · ');
    } else {
      $('definitionsStatus').textContent = `No definitions loaded: ${d.validReason}`;
      $('definitionsNote').textContent = '';
    }
    $('runtimeLine').textContent = s.runtimeLine || '';
    $('denylistLine').textContent = s.denylist
      ? (s.denylist.supported
        ? 'Denylist: this CLI enforces the definitions deny list.'
        : `Denylist: ${s.denylist.detail}`)
      : 'Denylist: unknown — no CLI found.';
    $('tripwireOnlyRow').classList.toggle('hidden', !(s.runtime && s.runtime.kind === 'none'));
    $('checkDir').value = s.settings.workdir || '';
    $('wallFolder').value = s.settings.workdir || '';
    $('confineFolderList').value = (s.settings.folders && s.settings.folders[0]) || s.settings.workdir || '';
    $('confineToggle').checked = !!s.settings.confine;
    $('confineFolders').classList.toggle('hidden', !s.settings.confine);
    selectedAgent = s.settings.agent || 'codex';
    for (const b of document.querySelectorAll('.agent-btn')) {
      b.classList.toggle('selected', b.dataset.agent === selectedAgent);
    }
    $('wallCommand').placeholder = `${selectedAgent === 'codex' ? 'codex' : selectedAgent === 'muse-code' ? 'muse' : 'claude'} exec "fix the bug in auth.ts"`;
    renderPolicyBox();
    renderSettings();
  });
}

function renderPolicyBox() {
  if (!status || !status.policy) { $('policyBox').textContent = ''; return; }
  const p = status.policy;
  const lines = [status.protectionLine];
  if (p.reasonLine) lines.push(p.reasonLine);
  lines.push(p.foldersLine, p.hostsLine, p.deniedLine);
  if (p.allowedCommandsLine) lines.push(p.allowedCommandsLine);
  if (p.boundsLine) lines.push(p.boundsLine);
  lines.push(p.scopeLine);
  $('policyBox').textContent = lines.join('\n');
}

function renderSettings() {
  if (!status) return;
  $('cliPath').value = status.settings.cliPath || '';
  $('settingsWorkdir').value = status.settings.workdir || '';
  $('cliStatus').textContent = status.cli
    ? `CLI found: ${status.cli.path} (${status.cli.mode})`
    : 'CLI not found — pick the fineprint executable, or install it and press Save.';
  const d = status.definitions;
  $('settingsDefinitions').textContent = d.version
    ? `Definitions v${d.version} (${d.source}), ${d.ruleCount} rules. ${d.valid ? 'In force as reported by the CLI.' : `Problem: ${d.validReason}`}`
    : `No definitions loaded: ${d.validReason}`;
  $('familyList').innerHTML = d.families.map((f) => `
    <p><strong>${esc(f.name)}</strong> — ${esc(f.plain || '')} <span class="muted">${esc((f.ruleIds || []).join(', '))}</span></p>`).join('');
  $('allowedCommands').value = (status.policy && status.policy.allowedCommands)
    ? status.policy.allowedCommands.join(', ') : '';
}

async function runCheck() {
  $('checkVerdict').innerHTML = '<p class="muted">Running the check…</p>';
  $('checkOutput').classList.add('hidden');
  try {
    const r = await fp.check($('checkDir').value || undefined);
    $('checkVerdict').innerHTML = verdictHtml(r.verdict)
      + (r.verdict.broken && r.verdict.broken.length ? `<p>Broken: ${esc(r.verdict.broken.join(', '))}</p>` : '')
      + (r.verdict.unmeasured && r.verdict.unmeasured.length ? `<p class="muted">Could not measure: ${esc(r.verdict.unmeasured.join(', '))}</p>` : '');
    $('checkOutput').textContent = `${r.stdout || ''}${r.stderr || ''}`;
    $('checkOutput').classList.remove('hidden');
    renderFeed();
  } catch (e) {
    $('checkVerdict').innerHTML = `<div class="verdict error"><h3>Could not run the check.</h3><p>${esc(e.message)}</p></div>`;
  }
}

async function runGuard() {
  $('wallVerdict').innerHTML = '<p class="muted">Running inside the wall…</p>';
  $('wallOutput').classList.add('hidden');
  $('wallAudit').innerHTML = '';
  $('wallNotifyNote').textContent = '';
  const folder = $('wallFolder').value;
  const command = $('wallCommand').value.trim().split(/\s+/).filter(Boolean);
  if (!command.length) {
    $('wallVerdict').innerHTML = '<div class="verdict error"><h3>No command.</h3><p>Type the command to run inside the wall.</p></div>';
    return;
  }
  try {
    const r = await fp.guard({
      agent: selectedAgent,
      folder,
      command,
      tripwireOnly: $('tripwireOnly').checked,
    });
    $('wallVerdict').innerHTML = verdictHtml(r.verdict);
    if (r.notified > 0) {
      $('wallNotifyNote').textContent = 'OS notification sent — check your Notification Center / Action Center.';
    }
    $('wallOutput').textContent = r.output || '';
    $('wallOutput').classList.remove('hidden');
    $('wallAudit').innerHTML = (r.auditLines || []).map((l) => `<p>${esc(l)}</p>`).join('') || '<p class="muted">No audit entries were written.</p>';
    renderFeed();
    await renderStatus();
  } catch (e) {
    $('wallVerdict').innerHTML = `<div class="verdict error"><h3>Could not run.</h3><p>${esc(e.message)}</p></div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  for (const b of document.querySelectorAll('.nav-btn')) {
    b.addEventListener('click', () => showView(b.dataset.view));
  }
  $('homeCheckBtn').addEventListener('click', () => showView('check'));
  $('homeWallBtn').addEventListener('click', () => showView('wall'));
  $('clearFeedBtn').addEventListener('click', async () => { await fp.clearFeed(); renderFeed(); });
  $('updateDefinitionsBtn').addEventListener('click', async () => {
    $('updateResult').textContent = 'Checking…';
    try {
      const r = await fp.checkDefinitions();
      $('updateResult').textContent = r.note || r.status;
    } catch (e) {
      $('updateResult').textContent = `Update check failed: ${e.message}`;
    }
  });
  $('runCheckBtn').addEventListener('click', runCheck);
  for (const b of document.querySelectorAll('.agent-btn')) {
    b.addEventListener('click', async () => {
      selectedAgent = b.dataset.agent;
      for (const x of document.querySelectorAll('.agent-btn')) x.classList.toggle('selected', x === b);
      $('wallCommand').placeholder = `${selectedAgent === 'codex' ? 'codex' : selectedAgent === 'muse-code' ? 'muse' : 'claude'} exec "fix the bug in auth.ts"`;
      await fp.saveSettings({ agent: selectedAgent });
    });
  }
  $('wallBrowseBtn').addEventListener('click', async () => {
    const f = await fp.pickFolder();
    if (f) { $('wallFolder').value = f; $('confineFolderList').value = f; }
  });
  $('confineToggle').addEventListener('change', async () => {
    const on = $('confineToggle').checked;
    $('confineFolders').classList.toggle('hidden', !on);
    const folders = $('confineFolderList').value ? [$('confineFolderList').value] : undefined;
    await fp.setConfinement(on, folders);
    await renderStatus();
  });
  $('runGuardBtn').addEventListener('click', runGuard);
  $('cliBrowseBtn').addEventListener('click', async () => {
    const f = await fp.pickCli();
    if (f) $('cliPath').value = f;
  });
  $('workdirBrowseBtn').addEventListener('click', async () => {
    const f = await fp.pickFolder();
    if (f) $('settingsWorkdir').value = f;
  });
  $('saveSettingsBtn').addEventListener('click', async () => {
    await fp.saveSettings({
      cliPath: $('cliPath').value || null,
      workdir: $('settingsWorkdir').value || null,
    });
    await fp.reinit();
    await renderStatus();
    $('settingsSaved').textContent = 'Saved.';
  });
  $('saveAllowedCommandsBtn').addEventListener('click', async () => {
    const list = $('allowedCommands').value.split(',').map((s) => s.trim()).filter(Boolean);
    await fp.setAllowedCommands(list);
    await renderStatus();
    $('settingsSaved').textContent = 'Saved.';
  });
  renderStatus().then(() => renderFeed());
});
