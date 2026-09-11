#source ./../../backend/core-service/.venv/bin/activate
#cd ./../../backend/core-service/src
#export PYTHONPATH="$PWD"
#echo $PYTHONPATH
#python --version
#python domains/common/models/mixins.py domains/management/models/base.py domains/management/models/contract.py > ../../../common/contracts/jsonschema/market_contract.json

source ./../../backend/core-service/.venv/bin/activate
export PYTHONPATH="$PWD"
echo $PYTHONPATH
python --version
python build_json_schemas.py -o ./../../common/contracts/jsonschema ./../../backend/core-service/src/domains/management/models
python build_json_schemas.py -o ./../../common/contracts/jsonschema ./../../backend/core-service/src/domains/management/commands
python build_json_schemas.py -o ./../../common/contracts/jsonschema ./../../backend/core-service/src/domains/risk/commands
