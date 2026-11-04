.PHONY: setup seed run test scale bench demo clean

PYTHON = ./.venv/Scripts/python.exe
PYTEST = ./.venv/Scripts/pytest.exe
UVICORN = ./.venv/Scripts/uvicorn.exe

# Fallbacks for Unix/macOS if run in bash
ifeq ($(OS),Windows_NT)
    PYTHON_CMD = .\.venv\Scripts\python.exe
    PYTEST_CMD = .\.venv\Scripts\pytest.exe
    UVICORN_CMD = .\.venv\Scripts\uvicorn.exe
else
    PYTHON_CMD = ./.venv/bin/python
    PYTEST_CMD = ./.venv/bin/pytest
    UVICORN_CMD = ./.venv/bin/uvicorn
endif

setup:
	python -m venv .venv
	$(PYTHON_CMD) -m pip install --upgrade pip
	$(PYTHON_CMD) -m pip install -r requirements.txt

seed:
	$(PYTHON_CMD) scripts/seed.py

run:
	$(UVICORN_CMD) app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(PYTEST_CMD) -v tests/

scale:
	$(PYTHON_CMD) scripts/generate_scale.py --users 500 --jobs 200000

bench:
	$(PYTHON_CMD) scripts/benchmark.py

demo:
	$(PYTHON_CMD) scripts/describe_access.py
