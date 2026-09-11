#!/bin/bash
BASE_DIR="frontend/web"
mkdir -p "$BASE_DIR"/{public,scripts,src/{app/{adapters,core/{api,auth,store},home,router},modules/{contracts/{pages,components,store,api},market-data/{pages,components,store,api},calculations/{pages,components,store,api},reports/{pages,components,store,api},visualizations/{pages,components,store,api}},shared/{api/generated,ui,lib,types,hooks},mocks/data,help/docs}}

touch "$BASE_DIR/src/main.tsx"
# Standard layout/sidebar/auth/help mechanics live in frontend/app-shell.
