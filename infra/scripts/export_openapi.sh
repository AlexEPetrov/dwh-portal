source ./../../backend/core-service/.venv/bin/activate
export PYTHONPATH="$PWD:./../../backend/core-service/src"
echo $PYTHONPATH
python --version

cd ./../../backend/core-service

# Export the OpenAPI spec
python -c "
import json
from pathlib import Path

from fastapi import FastAPI

output_path = Path('./../../common/contracts/openapi/openapi.json')

try:
    from api.host import app
    spec = app.openapi()
except Exception:
    from api.portal import portal_router
    portal_app = FastAPI()
    portal_app.include_router(portal_router)
    portal_spec = portal_app.openapi()
    spec = json.loads(output_path.read_text(encoding='utf-8')) if output_path.exists() else {'openapi': '3.1.0', 'info': {'title': 'FastAPI', 'version': '0.1.0'}, 'paths': {}, 'components': {'schemas': {}}}
    spec.setdefault('paths', {}).update(portal_spec.get('paths', {}))
    spec.setdefault('components', {}).setdefault('schemas', {}).update(
        portal_spec.get('components', {}).get('schemas', {})
    )
    tags = spec.setdefault('tags', [])
    existing = {tag.get('name') for tag in tags if isinstance(tag, dict)}
    for tag in portal_spec.get('tags', []):
        if tag.get('name') not in existing:
            tags.append(tag)

with output_path.open('w', encoding='utf-8') as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)
print(f'OpenAPI spec exported to {output_path}')
"

echo "Done!"
