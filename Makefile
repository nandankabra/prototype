.PHONY: demo test stop samples

demo:
	docker compose up --build -d --wait
	docker compose exec backend python -m app.seed
	@echo "ByteCode Verify: http://localhost:3000"

test:
	docker compose exec backend pytest

samples:
	docker compose exec backend python sample-docs/generate_samples.py
	mkdir -p sample-docs/generated
	docker compose cp backend:/app/sample-docs/generated/. sample-docs/generated/

stop:
	docker compose down
