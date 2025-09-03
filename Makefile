.PHONY: help setup install run migrate superuser test load-sample clean

# Default Python and pip commands
PYTHON := python
PIP := pip
MANAGE := $(PYTHON) manage.py

# Help command
help:
	@echo "Available commands:"
	@echo "  setup        Complete development setup (install + migrate)"
	@echo "  install      Install dependencies"
	@echo "  run          Start the development server"
	@echo "  migrate      Run database migrations"
	@echo "  superuser    Create a superuser"
	@echo "  test         Run test suite"
	@echo "  load-sample  Load sample POI data from ../data/"
	@echo "  clean        Clean up cache and temporary files"

# Development setup
setup: install migrate
	@echo "Development setup complete!"
	@echo "Next steps:"
	@echo "  make load-sample  # Load sample data"
	@echo "  make superuser    # Create admin user"
	@echo "  make run          # Start development server"

install:
	$(PIP) install -r requirements.txt

# Database operations
migrate:
	$(MANAGE) makemigrations
	$(MANAGE) migrate

superuser:
	$(MANAGE) createsuperuser

# Development server
run:
	$(MANAGE) runserver

# Testing
test:
	$(MANAGE) test

# Data operations
load-sample:
	@echo "Loading sample POI data from ../data/"
	@if [ -d "../data" ]; then \
		$(MANAGE) import_poi ../data/ --verbose; \
		echo "Sample data loaded successfully!"; \
		echo ""; \
		echo "Data summary:"; \
		$(MANAGE) shell -c "from ingest.models import PointOfInterest; print(f'Total POIs: {PointOfInterest.objects.count()}'); print(f'Categories: {PointOfInterest.objects.values_list(\"category\", flat=True).distinct().count()}'); print(f'Sources: {list(PointOfInterest.objects.values_list(\"source\", flat=True).distinct())}')"; \
	else \
		echo "Error: ../data/ directory not found"; \
		echo "Please ensure the data directory exists with sample files:"; \
		echo "  ../data/pois.csv"; \
		echo "  ../data/JsonData.json"; \
		echo "  ../data/XmlData.xml"; \
	fi

# Utility commands
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf build/ dist/

# Development workflow shortcuts
dev: setup load-sample
	@echo "Development environment ready!"
	@echo "Access the application at:"
	@echo "  Admin: http://localhost:8000/admin/"
	@echo "  API:   http://localhost:8000/api/poi/"
	@echo "  Health: http://localhost:8000/health/"

# Quick commands for common tasks
shell:
	$(MANAGE) shell

dbshell:
	$(MANAGE) dbshell

collectstatic:
	$(MANAGE) collectstatic --noinput
