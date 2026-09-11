FROM 134/python-base-313:1.0

RUN pip install ruff==0.9.10
RUN pip install pytest==8.3.5
RUN pip install pytest-cov==5.0.0
RUN pip install pytest-bdd

RUN python --version
 