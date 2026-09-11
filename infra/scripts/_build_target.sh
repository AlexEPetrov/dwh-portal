if [[ ! -v CI_ENVIRONMENT ]]; then
    echo "CI_ENVIRONMENT is not set. Shoud be either test or prod or local, etc"
    exit -1
fi

cd ..
cd ..

mkdir -p ./.build
rm -rf ./.build/$CI_ENVIRONMENT
mkdir -p ./.build/$CI_ENVIRONMENT
mkdir -p ./.build/$CI_ENVIRONMENT/migrations

# сборка фронта

cd ./frontend
cd ./web 
npm run build 
cd ..
cd ..



# frontend-dist для FastAPI SPA fallback (/app/frontend-dist)
# Берем собранный фронт из frontend/web/dist, если он существует.
echo "============================================================================="
rm -rf ./backend/core-service/frontend-dist
if [ -d ./frontend/web/dist ]; then
    mkdir -p ./backend/core-service/frontend-dist
    cp -r ./frontend/web/dist/* ./backend/core-service/frontend-dist/
    echo "[INFO] frontend-dist copied to backend/core-service/frontend-dist"
else
    echo "[WARN] frontend/web/dist not found, frontend-dist will not be included"
fi

# далее сборка образов

cd ./backend/core-service

find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +

./build_image.sh
cd ..
cd ..

# генерация миграций - забираем из СОБРАННОГО образа!

docker create --name=temp-pvs-core-service 134/pvs-core-service:1.2
docker cp temp-pvs-core-service:/app/migrations/all.sql ./.build/$CI_ENVIRONMENT/migrations/all.sql
docker rm temp-pvs-core-service

# Копируем все что считаем артифактом

cp ./infra/environments/$CI_ENVIRONMENT ./.build -r
cp ./infra/environments/$CI_ENVIRONMENT/.env ./.build/$CI_ENVIRONMENT
#cp ./infra/migrations ./.build/$CI_ENVIRONMENT -r
cp ./infra/compose/docker-compose*.yml ./.build/$CI_ENVIRONMENT
cp ./backend/core-service/src ./.build/$CI_ENVIRONMENT -r
cp ./backend/core-service/frontend-dist ./.build/$CI_ENVIRONMENT -r 

# сохраняем образа

cd ./.build/$CI_ENVIRONMENT
docker save -o ./pvs-core-service.img 134/pvs-core-service:1.2
docker save -o ./pvs-calc-service.img 134/pvs-calc-service:1.2
git rev-parse HEAD > commit-sh.txt





