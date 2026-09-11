docker build . --file ./python-base-image.Dockerfile -t 134/python-base-313:1.0
docker build . --file ./python-builder-image.Dockerfile -t 134/python-builder-313:1.0
docker build . --file ./python-slim-image.Dockerfile -t 134/python-slim-313:1.0
