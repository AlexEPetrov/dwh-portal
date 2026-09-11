
# Настройка переменных
VERSION="v1.5.2"
PLATFORM="linux_amd64"
TARGET_DIR="duckdb_extensions/${VERSION}/${PLATFORM}"

# Создание дерева папок
mkdir -p "$TARGET_DIR"

curl -fL -o duckdb_extensions/v1.5.2/linux_amd64/parquet.duckdb_extension.gz  https://duckdb.org
curl -fL -o duckdb_extensions/v1.5.2/linux_amd64/httpfs.duckdb_extension.gz https://duckdb.org

echo "=== Скачивание завершено! Проверьте папку duckdb_extensions. Скопируйте в core-service/duckdb_extensions. ==="

