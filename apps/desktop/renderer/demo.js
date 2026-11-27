'use strict';
/* Scripted demo driver — runs ONLY when the app is launched with
 * --demo (renderer URL carries ?demo=1) or --demo-s1 (?demo=s1).
 * --demo drives the real UI with real clicks and typing against the
 * real CLI:
 *   Home (definitions) -> Check -> Wall (pick codex, pick folder,
 *   run a command that reads the protected records file) -> the block
 *   (DENY-RECORDS, deny mode — no confinement needed) -> Home (the
 *   feed shows it).
 * --demo-s1 shows the Home feed seeded from a recorded real gate log
 * (see runS1 below) — a replay, not a live model run.
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
  const mode = params.get('demo');
  if (mode !== '1' && mode !== 's1') return;
  const demoDir = params.get('demodir') || '';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (id) => document.getElementById(id);
  const log = (...a) => console.log('[fp-demo]', ...a);

  function finish() {
    document.title = 'FinePrint demo — done';
    if (window.fineprint && window.fineprint.demoDone) {
      window.fineprint.demoDone().catch(() => {});
    }
  }

  /* Second-opinion demo (?demo=s1): the Home feed, seeded by main.js
   * from a RECORDED real gate log (assets/demo-second-opinion-log.jsonl
   * — entries the real gate wrote with the real bekko model). It is a
   * replay, not a live model run: the model takes ~2 minutes to load.
   * The screen shows, top to bottom: the feed summary (deterministic
   * denials counted apart from second-opinion verdicts), a
   * second-opinion allow (the false-negative candidate), a
   * second-opinion block (probabilistic label + model + version +
   * reason), and a deterministic DENY-RECORDS block (rule +
   * "this will always be blocked") for contrast. PACE (Anish, Nov 7):
   * SLOW — the feed is held long enough to read every line.
   * Nothing else is driven: the feed is the demo. */
  async function runS1() {
    try {
      await waitFor(() => document.querySelectorAll('#feedList .feed-item').length > 0, 15000, 'seeded feed items');
      log('second-opinion feed shown:',
        document.querySelectorAll('#feedList .feed-item').length, 'items');
      // Hold the top of the feed (the summary + the newest verdicts)
      // so every line can be read clearly.
      await sleep(7000);
      // The feed is taller than the window: scroll down so the
      // remaining verdicts (the model block, the deterministic block)
      // are readable too, then back to the top for the final hold.
      window.scrollTo(0, document.body.scrollHeight);
      await sleep(7000);
      window.scrollTo(0, 0);
      await sleep(6000);
      log('demo complete');
    } catch (e) {
      log('demo error:', e && e.message);
    } finally {
      finish();
    }
  }

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
      finish();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mode === 's1' ? runS1 : run);
  } else if (mode === 's1') {
    runS1();
  } else {
    run();
  }
}());
