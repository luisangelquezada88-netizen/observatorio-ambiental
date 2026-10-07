.PHONY: up down logs verify dashboard test extract transform load

FECHA ?= $(shell powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd)")
PYTHON ?= python

up:
	docker compose up -d
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

test:
	$(PYTHON) -m pytest tests/ -q

extract:
	$(PYTHON) -m src.extract.openmeteo_meteorologia --fecha $(FECHA)
	$(PYTHON) -m src.extract.openmeteo_calidad_aire --fecha $(FECHA)
	$(PYTHON) -m src.extract.openmeteo_hidrologia --fecha $(FECHA)

transform:
	$(PYTHON) -m src.transform.indicadores --fecha $(FECHA)

load:
	$(PYTHON) -m src.load.postgis --fecha $(FECHA)

verify:
	$(PYTHON) -m pytest tests/ -q
	$(PYTHON) scripts/verify_idempotencia.py --fecha $(FECHA) || $(PYTHON) -m src.transform.indicadores --fecha $(FECHA)

dashboard:
	quarto render dashboard --to html

init-db:
	psql "host=localhost port=5433 dbname=ambiental user=ambiental password=ambiental_dev" -f sql/01_schema_postgis.sql
