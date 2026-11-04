import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluate import evaluate

EMPTY = {"user": {}, "smart_approve": {}}
ASK = {"user": {"developer__shell": "prompt"}, "smart_approve": {}}
DENY = {"user": {"developer__shell": "forbidden"}, "smart_approve": {}}
ALLOW = {"user": {"developer__shell": "allow"}, "smart_approve": {}}
SMART_ASK = {"user": {}, "smart_approve": {"developer__shell": "prompt"}}

def check(cond, label):
    assert cond, label
    print("ok:", label)

check(evaluate("rm -rf x", EMPTY, "auto")["decision"] == "allow", "auto+empty -> allow (default)")
check(evaluate("rm -rf x", DENY, "auto")["decision"] == "forbidden", "auto+deny -> forbidden (deny overrides)")
check(evaluate("cat x", ASK, "approve")["decision"] == "prompt", "approve+ask -> prompt")
check(evaluate("cat x", EMPTY, "approve")["decision"] == "prompt", "approve+empty -> prompt")
check(evaluate("rm -rf x", DENY, "approve")["decision"] == "forbidden", "approve+deny -> forbidden")
check(evaluate("cat x", ALLOW, "approve")["decision"] == "allow", "approve+allow -> allow")
check(evaluate("ls", EMPTY, "smart_approve")["decision"] == "prompt", "smart+empty shell -> prompt (judge ceiling noted)")
check(evaluate("ls", SMART_ASK, "smart_approve")["decision"] == "prompt", "smart+smart-category ask -> prompt")
check(evaluate("rm -rf x", EMPTY, "chat")["decision"] == "unknown", "chat -> unknown, never allow/forbidden")
check(evaluate("rm -rf /tmp/sbx/target.txt", ASK, "approve")["decision"]
      == evaluate("cat /tmp/sbx/target.txt", ASK, "approve")["decision"], "tool granularity: rm and cat decide alike")
print("ALL GOOSE ENGINE TESTS PASS")
