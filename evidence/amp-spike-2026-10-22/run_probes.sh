#!/bin/bash
# Amp second-oracle spike probes. Settings: corpus-policy.json (corpus-analogous user rules).
AMP="./amp-home/bin/amp"
S="corpus-policy.json"
i=0
while IFS= read -r cmd; do
  i=$((i+1))
  id=$(printf "P-%02d" $i)
  HOME="$PWD/fakehome" AMP_HOME="$PWD/amp-home" timeout 60 $AMP --settings-file $S permissions test --json Bash --cmd "$cmd" > "raw/${id}.run$RUN.json" 2>"raw/${id}.run$RUN.stderr"
  echo "$id :: $cmd -> $(python3 -c "import json;d=json.load(open('raw/${id}.run$RUN.json'));print(d.get('action'),d.get('source'))")"
done <<'CMDS'
git status
rm -rf /tmp/x
rm --recursive --force /tmp/x
/bin/rm -rf /tmp/x
bash -lc rm -rf /
env rm -rf /tmp/x
sudo -E rm -rf /tmp/x
env FOO=bar rm -rf /tmp/x
deployctl release production
rm -rf /records/health/2024
ls /records/health
curl https://example.com
xyzzyplugh --frobnicate
CMDS
