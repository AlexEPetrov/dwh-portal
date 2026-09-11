source ./backend/.venv/bin/activate
cd ./backend/src
alembic upgrade --sql head > ./../../deployment/migrations/all.sql
cd ..
cd ..



