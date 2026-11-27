"""The demo steps: real commands, in order, with the pause (seconds)
after each command's output so a viewer can read it before the next
command is typed.

Every command runs for real in the recording pty; the recorder only
controls typing speed (TYPE_DELAY_MS per character) and the pauses.
Total target: 60-120 seconds.
"""

TYPE_DELAY_MS = 45

STEPS = [
    {
        "cmd": "echo \"FinePrint — live harness + attribution (branch-only demo)\"",
        "pause": 4,
    },
    {
        "cmd": "python3 tools/live_run.py list-harnesses",
        "pause": 5,
    },
    {
        "cmd": "python3 tools/live_run.py status --harness cursor",
        "pause": 5,
    },
    {
        "cmd": ("python3 tools/live_run.py verify --bundle "
                "framework/scorecard/cursor-pilot-v1/bundle.json"),
        "pause": 4,
    },
    {
        "cmd": ("python3 tools/demo/explain_bundle.py "
                "framework/scorecard/cursor-pilot-v1/bundle.json"),
        "pause": 9,
    },
    {
        "cmd": ("python3 tools/demo/explain_bundle.py "
                "framework/scorecard/cursor-pilot-v1/bundle.json --story"),
        "pause": 9,
    },
    {
        "cmd": "python3 tools/demo/show_attribution.py",
        "pause": 10,
    },
    {
        "cmd": ("echo \"Replay only — the live run happened on GitHub Actions, "
                "key in repo secrets.\""),
        "pause": 4,
    },
]
