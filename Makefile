.PHONY: install install-app test experiments experiments-quick real app figures clean fetch-data

install:
	python -m pip install -r requirements.txt -r requirements-dev.txt

install-app:
	python -m pip install -r requirements-app.txt

test:
	python -m pytest

experiments:
	python scripts/run_experiments.py

experiments-quick:
	python scripts/run_experiments.py --quick

figures:
	python scripts/make_figures.py

real:
	python -m qcom.cli real --out reports/real_city.json

fetch-data:
	python scripts/fetch_osm_density.py
	python scripts/fetch_order_timing.py

app:
	streamlit run app/wargame.py

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache
	find . -name '*.pyc' -delete
