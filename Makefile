.PHONY: setup seed run run-scale test scale bench demo clean

ifeq ($(OS),Windows_NT)
    PYTHON_CMD = .\.venv\Scripts\python.exe
    PYTEST_CMD = .\.venv\Scripts\pytest.exe
    UVICORN_CMD = .\.venv\Scripts\uvicorn.exe
    SET_SCALE_DB = set DATABASE_URL=sqlite:///./scale.db &&
else
    PYTHON_CMD = ./.venv/bin/python
    PYTEST_CMD = ./.venv/bin/pytest
    UVICORN_CMD = ./.venv/bin/uvicorn
    SET_SCALE_DB = DATABASE_URL=sqlite:///./scale.db
endif

setup:
	python -m venv .venv
	$(PYTHON_CMD) -m pip install --upgrade pip
	$(PYTHON_CMD) -m pip install -r requirements.txt

seed:
	$(PYTHON_CMD) scripts/seed.py

run:
	$(UVICORN_CMD) app.main:app --host 0.0.0.0 --port 8000 --reload

run-scale:
	$(SET_SCALE_DB) $(UVICORN_CMD) app.main:app --host 0.0.0.0 --port 8000

test:
	$(PYTEST_CMD) -v tests/

scale:
	$(PYTHON_CMD) scripts/generate_scale.py --users 500 --jobs 200000 --db sqlite:///./scale.db

bench:
	$(PYTHON_CMD) scripts/benchmark.py --db sqlite:///./scale.db

demo:
	bash scripts/demo.sh
