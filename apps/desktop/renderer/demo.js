'use strict';
/* Scripted demo driver — runs ONLY when the app is launched with
 * --demo (renderer URL carries ?demo=1). It drives the real UI with
 * real clicks and typing against the real CLI:
 *   Home (definitions) -> Check -> Wall (pick codex, pick folder,
 *   run a command that reads the protected records file) -> the block
 *   (DENY-RECORDS, deny mode — no confinement needed) -> Home (the
 *   feed shows it).
 * PACE (Anish, Nov 7): SLOW — roughly 2-3x a normal walkthrough.
 * Every step pauses long enough to read every line, button, and
 * notification on screen before the next one, and the demo ENDS on
 * the Home feed (the blocked entries) held for ten seconds, so the
 * final blocked-notification screen can be read clearly.
 * Nothing is faked: the guarded command really runs through the real
 * wall and the block, feed entry, and OS notification are real.
 * The flow ends by setting document.title to "FinePrint demo — done"
 * so the recording script knows when to stop capturing.
 * See docs/RECORDING.md for how to record the GIF. */
(function () {
  const params = new URLSearchParams(window.location.search);
  if (params.get('demo') !== '1') return;
  const demoDir = params.get('demodir') || '';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (id) => document.getElementById(id);
  const log = (...a) => console.log('[fp-demo]', ...a);

  async function waitFor(fn, timeoutMs, label) {
    const start = Date.now();
    for (;;) {
      try { if (fn()) return true; } catch { /* keep waiting */ }
      if (Date.now() - start > timeoutMs) { log('timeout waiting for', label); return false; }
      await sleep(250);
    }
  }

  async function run() {
    try {
      // SLOW pace: every hold is long enough to read the screen.
      await sleep(7000); // Home: definitions card + empty feed.
      log('going to Check');
      document.querySelector('[data-view="check"]').click();
      await sleep(2000);
      $('runCheckBtn').click();
      await waitFor(() => document.querySelector('#checkVerdict .verdict'), 60000, 'check verdict');
      await sleep(6000); // Read the verdict.

      log('going to the Wall');
      document.querySelector('[data-view="wall"]').click();
      await sleep(3000);
      document.querySelector('[data-agent="codex"]').click();
      await sleep(3000);
      // The protected records file (V1-20): reading it is denied by
      // DENY-RECORDS in deny mode — no confinement needed.
      const records = demoDir ? `${demoDir}/work/records.txt` : 'records.txt';
      $('wallCommand').value = `cat ${records}`;
      log('command set to', $('wallCommand').value);
      await sleep(3000); // Read the picked agent, folder, and command.
      $('runGuardBtn').click();
      await waitFor(() => document.querySelector('#wallVerdict .verdict'), 60000, 'wall verdict');
      await sleep(7000); // Read the block banner + audit log.

      log('back Home to the feed');
      document.querySelector('[data-view="home"]').click();
      await waitFor(() => document.querySelectorAll('#feedList .feed-item').length > 0, 15000, 'feed items');
      // Final screen: the blocked entries in the feed. Held for ten
      // seconds so every line can be read clearly.
      await sleep(10000);
      log('demo complete');
    } catch (e) {
      log('demo error:', e && e.message);
    } finally {
      document.title = 'FinePrint demo — done';
      if (window.fineprint && window.fineprint.demoDone) {
        window.fineprint.demoDone().catch(() => {});
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
}());
