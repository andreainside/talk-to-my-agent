#!/usr/bin/env bash
# Release gate. Two releases shipped broken because nothing proved a real agent
# could start; this makes that impossible to skip.
#
#   ./release.sh v0.8.0
set -euo pipefail
TAG="${1:?usage: ./release.sh vX.Y.Z}"

grep -q "^## $TAG " CHANGELOG.md || { echo "✗ CHANGELOG.md has no '## $TAG' section — write it first"; exit 1; }

echo "→ permission policy"; python3 test_permissions.py >/dev/null
echo "→ topic routing";     python3 test_routing.py >/dev/null
echo "→ live agent launch"; python3 test_launch.py | tail -3

echo "→ leaked identifiers"
if grep -rnoE "ou_[a-z0-9]{16,}|oc_[a-z0-9]{16,}|cli_[a-z0-9]{12,}" --include="*.py" --include="*.md" --include="*.json" . \
   | grep -v "ou_YOUR\|oc_LAUNCHTEST" ; then
  echo "✗ real Feishu ids found above — scrub before releasing"; exit 1
fi

git diff --quiet || { echo "✗ uncommitted changes"; exit 1; }
git tag -a "$TAG" -m "$TAG"
git push -q && git push -q --tags
python3 -c "import sys; sys.path.insert(0,'.'); import bridge; open('/tmp/rn.md','w').write(bridge.changelog_entry('$TAG'))"
gh release create "$TAG" --title "$TAG" --notes-file /tmp/rn.md
echo "✓ released $TAG"
