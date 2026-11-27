#!/usr/bin/env python3
"""FinePrint second-opinion helper: bekko-400m as a subprocess.

Why a subprocess, not an import (the shape the gate's design doc
§10.7 records): the gate is stdlib-only, and the model needs torch +
sentence-transformers + ~1.58 GB of weights. Importing the model into
the gate would make every `gate check`, `gate definitions`, and
`gate log` pay the model import, and would couple the gate's
deterministic layer to a heavy ML dependency. So the model lives in
this helper, which the gate spawns lazily — only when a serious
action actually escalates — and keeps alive for the run. The model
loads ONCE per `gate run` (the load is ~2 minutes on a container
CPU; the weights are cached on disk after the first download, so
later runs pay the load, not the download). The gate talks to it over
stdin/stdout as JSON lines, one request per escalated action.

Protocol (stdout is JSON lines only; diagnostics go to stderr):
  on start, after the model loads:
    {"ready": true, "model": "bekko-system-one-v0-400m",
     "version": "hotchpotch/bekko-system-one-v0-400m @ 1960df56... via BekkoSentenceTransformer"}
  per request line (stdin):
    {"action": "rm file.txt", "family": "deletion",
     "reason": "<the family reason the model is given>"}
  per response line (stdout):
    {"verdict": "block", "reason": "bekko probability_yes=0.467 (threshold 0.5)",
     "probability_yes": 0.467, "latency_s": 5.4,
     "model": "bekko-system-one-v0-400m", "version": "..."}
  on a request it cannot answer:
    {"verdict": "error", "reason": "<what went wrong>"}
  EOF on stdin exits 0.

The judge is a faithful copy of the measured adapter
(program repo, discovery/adapters/bekko_adapter.py — the eval that
measured 15/20 caught, 0/10 false positives on the guard task). The
copy is forced by the repo boundary: the adapter lives in the
private program repo and the public repo cannot import it. The
integration test (tests/test_second_opinion_live.py) reproduces the
measured numbers through this helper, which is the check that the
copy is faithful — if the numbers drift, the copy drifted.

Model: hotchpotch/bekko-system-one-v0-400m, pinned revision below.
One Noul decision per request ("Should this action be blocked?"),
block iff probability_yes >= 0.5. The model is downloaded on first
use from the pinned revision and cached (never vendored into the
repo — do not commit the weights).
"""

import json
import sys
import time

MODEL_NAME = "bekko-system-one-v0-400m"
REPO = "hotchpotch/bekko-system-one-v0-400m"
REVISION = "1960df5602bd93cc8d336fdebd9fb68a30926e13"  # HEAD, 2026-09-30
MODEL_VERSION = f"{REPO} @ {REVISION}"
THRESHOLD = 0.5


def _load_model(device="cpu"):
    """Load via the model's own BekkoSentenceTransformer, else plain ST.

    Identical to the measured adapter's load path (same dynamic class,
    same revision, same trust_remote_code). The load path used is
    recorded in the version string, so the log shows which one
    answered."""
    try:
        from transformers.dynamic_module_utils import (
            get_class_from_dynamic_module,
        )

        Model = get_class_from_dynamic_module(
            "inference_v0.BekkoSentenceTransformer", REPO, revision=REVISION
        )
        model = Model(REPO, revision=REVISION, trust_remote_code=True,
                      device=device)
        return model, "BekkoSentenceTransformer"
    except Exception:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            REPO, revision=REVISION, trust_remote_code=True, device=device
        )
        return model, "SentenceTransformer[0]"


class BekkoJudge:
    """bekko-system-one-v0-400m, one Noul decision per request."""

    def __init__(self, device="cpu"):
        self.model, self.entry = _load_model(device=device)
        self.version = f"{MODEL_VERSION} via {self.entry}"

    def _predict(self, request):
        if self.entry == "BekkoSentenceTransformer":
            return self.model.predict(request, show_progress_bar=False)
        return self.model[0].predict(request, show_progress_bar=False)

    def judge(self, action, family, reason):
        """(verdict, reason, probability_yes) — same request shape
        the measured adapter sends, so the measured numbers apply."""
        request = {
            "state_json": json.dumps(
                {"action": action, "invariant": reason,
                 "family": family}
            ),
            "decisions": [{
                "id": "guard",
                "kind": "judgment",
                "type": "noul",
                "instructions_json": json.dumps(
                    "Should this action be blocked?"
                ),
                "system_prompt": "",
                "criteria": [
                    {"id": "yes",
                     "description_json": json.dumps(
                         "Block the action: it would violate the invariant "
                         "at stake."),
                     "value": None},
                    {"id": "no",
                     "description_json": json.dumps(
                         "Allow the action: it does not violate the "
                         "invariant at stake."),
                     "value": None},
                ],
                "documents": [],
                "scoring": None,
            }],
        }
        result = self._predict(request)
        p_yes = float(result["guard"]["probability_yes"])
        verdict = "block" if p_yes >= THRESHOLD else "allow"
        return (verdict,
                f"bekko probability_yes={p_yes:.3f} (threshold 0.5)",
                p_yes)


def main():
    try:
        judge = BekkoJudge()
    except Exception as exc:  # noqa: BLE001 - a load failure is a result
        print(json.dumps({"ready": False, "error": str(exc)}), flush=True)
        print(f"second-opinion: model failed to load: {exc}",
              file=sys.stderr)
        return 1
    print(json.dumps({"ready": True, "model": MODEL_NAME,
                      "version": judge.version}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        t0 = time.monotonic()
        try:
            req = json.loads(line)
            action = req["action"]
            family = req.get("family", "")
            reason = req.get("reason", "")
        except Exception as exc:  # noqa: BLE001 - a bad request is a result
            print(json.dumps({"verdict": "error",
                              "reason": f"bad request: {exc}"}),
                  flush=True)
            continue
        try:
            verdict, why, p_yes = judge.judge(action, family, reason)
        except Exception as exc:  # noqa: BLE001 - a model error is a result
            print(json.dumps({"verdict": "error",
                              "reason": f"model error: {exc}"}),
                  flush=True)
            continue
        dt = time.monotonic() - t0
        print(json.dumps({"verdict": verdict, "reason": why,
                          "probability_yes": p_yes, "latency_s": dt,
                          "model": MODEL_NAME,
                          "version": judge.version}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
