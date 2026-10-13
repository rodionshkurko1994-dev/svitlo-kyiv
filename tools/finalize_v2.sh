#!/bin/bash
# Rebuild the map with per-building YASNO groups and stage it for publishing.
set -e
cd /home/claude/svitlo-kyiv
git pull -q --rebase origin main
ls data/full/groups_*.json
cd /home/claude/kyiv/osm
python3 -I build_v2.py /home/claude/svitlo-kyiv/data 2>&1 | grep -v -i "deprecat\|shapely.ops.transform\|u = unary\|city_ring =" | tail -5
mkdir -p /home/claude/kyiv/v2 && cd /home/claude/kyiv/v2
base64 -w0 ../osm/kyiv3d_v2.bin > city_v2.txt
python3 -I ../osm/patch_v2.py /home/claude/svitlo-kyiv/index.html index.html ../osm/meta_v2.json city_v2.txt
python3 -I ../osm/patch_v2.py /home/claude/kyiv/site/kyiv-light.html artifact.html ../osm/meta_v2.json city_v2.txt
node -e "for (const f of ['index.html','artifact.html']) { const h=require('fs').readFileSync(f,'utf8'); new Function(h.split('<script>')[1].split('</script>')[0]); } console.log('syntax ok')"
