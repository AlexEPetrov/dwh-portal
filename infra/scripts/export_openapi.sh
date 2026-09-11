source ./../../backend/core-service/.venv/bin/activate
export PYTHONPATH="$PWD;./../../backend/core-service/src"
echo $PYTHONPATH
python --version

cd ./../../backend/core-service

# Export the OpenAPI spec
python -c "
import json
import sys
from api.host import app
spec = app.openapi()
output_path = './../../common/contracts/openapi/openapi.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)
print(f'OpenAPI spec exported to {output_path}')
"

echo "Done!"
