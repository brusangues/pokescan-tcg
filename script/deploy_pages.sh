#!/usr/bin/env bash
# ============================================================
# deploy_pages.sh — publica o frontend estático no GitHub Pages
# (branch gh-pages). Deve rodar do PC (os dados estão locais).
#
#   bash script/deploy_pages.sh
#
# Passos: 1) build_static_data.py (CSVs → public/data/*.json)
#         2) next build com NEXT_PUBLIC_BASE_PATH=/pokescan-tcg
#            usando Node 20 (Node 22 QUEBRA o export no Windows:
#            "workUnitAsyncStorage" — vercel/next.js#95543)
#         3) push do out/ para a branch gh-pages
# ============================================================
set -euo pipefail

# Caminhos Windows-style (o MSYS bagunça caminhos POSIX em args de .exe)
REPO_DIR_W="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || cygpath -w "$(cd "$(dirname "$0")/.." && pwd)")"
FRONTEND_W="$REPO_DIR_W\\frontend"
OUT_W="$FRONTEND_W\\out"
NODE20="/c/Models/hermes/node-v20.20.2-win-x64/node.exe"
PYTHON="C:/Models/hermes/hermes-agent/venv/Scripts/python.exe"
REMOTE="https://github.com/brusangues/pokescan-tcg.git"

echo "==> 1/4 Gerando dados estáticos (public/data)"
"$PYTHON" "$REPO_DIR_W\\script\\build_static_data.py"

echo "==> 2/4 Build Next.js (Node 20)"
cd "$FRONTEND_W" 2>/dev/null || cd /c/projects/pokescan-tcg/frontend
rm -rf .next out
NEXT_PUBLIC_BASE_PATH=/pokescan-tcg \
  PATH="$(dirname "$NODE20"):$PATH" \
  "$NODE20" node_modules/next/dist/bin/next build

echo "==> 3/4 Preparando out/ (".nojekyll" + git)"
touch "$OUT_W\\.nojekyll" 2>/dev/null || touch "$(cygpath -u "$OUT_W")/.nojekyll"
cd "$(cygpath -u "$OUT_W")"
git init -q 2>/dev/null || true
git checkout -q -b gh-pages 2>/dev/null || git checkout -q gh-pages 2>/dev/null || true
git add -A
git -c user.name="pokescan-deploy" -c user.email="deploy@localhost" \
  commit -qm "deploy $(date +%Y-%m-%d_%H%M)" || echo "  (sem mudanças para commitar?)"

echo "==> 4/4 Push para gh-pages"
git push -f "$REMOTE" HEAD:gh-pages

echo ""
echo "OK — publicado em https://brusangues.github.io/pokescan-tcg/"
