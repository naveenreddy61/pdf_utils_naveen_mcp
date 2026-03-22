# ── PDF Utils – Common Workflows ─────────────────────────────────────────────
# Usage: make <target>
# Requires: uv (https://docs.astral.sh/uv/)

.PHONY: help dev install sync restart stop logs logs-100 logs-nginx test \
        install-playwright chrome-path build clean push deploy status

help:
	@echo "PDF Utils – available targets:"
	@echo ""
	@echo "  Development"
	@echo "    dev               Start local dev server (port 8000)"
	@echo "    install           Install all dependencies (uv sync)"
	@echo "    sync              Alias for install"
	@echo "    install-playwright  Install Playwright + headless Chromium"
	@echo "    chrome-path       Print the Playwright Chromium binary path"
	@echo ""
	@echo "  Testing"
	@echo "    test              Run OCR service test suite"
	@echo "    test-env          Verify environment (API key, Google GenAI)"
	@echo ""
	@echo "  VPS Service (pdf-app systemd)"
	@echo "    restart           Restart the VPS service"
	@echo "    stop              Stop the VPS service"
	@echo "    status            Show service status"
	@echo "    logs              Tail live service logs"
	@echo "    logs-100          Show last 100 log lines"
	@echo "    logs-nginx        Tail live nginx access log"
	@echo ""
	@echo "  Build & Deploy"
	@echo "    build             Build distributable wheel"
	@echo "    push              git push current branch"
	@echo "    deploy            push + restart VPS service"
	@echo ""
	@echo "  Maintenance"
	@echo "    clean             Remove build artifacts and temp files"
	@echo "    db-stats          Show OCR cache database statistics"
	@echo "    db-clear          Delete OCR cache database (forces re-OCR)"

# ── Development ───────────────────────────────────────────────────────────────

dev:
	uv run app.py

install sync:
	uv sync

install-playwright:
	@echo "Installing Playwright Python package..."
	uv add playwright
	@echo "Downloading headless Chromium browser..."
	uv run playwright install chromium
	@echo "Installing Chromium system dependencies..."
	uv run playwright install-deps chromium
	@echo ""
	@echo "Done. Verify with: make chrome-path"

chrome-path:
	@uv run python -c "from playwright.sync_api import sync_playwright; \
	    p = sync_playwright().start(); \
	    print(p.chromium.executable_path); \
	    p.stop()"

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	uv run python tests/test_ocr_service.py

test-env:
	@echo "Checking Google GenAI client..."
	uv run python -c "from google import genai; print('✅ Google GenAI importable')"
	@echo "Checking API key..."
	uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); \
	    key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'); \
	    print('✅ API key found') if key else print('❌ No API key – set GOOGLE_API_KEY in .env')"
	@echo "Checking Playwright / Chromium..."
	uv run python -c "from playwright.sync_api import sync_playwright; \
	    p = sync_playwright().start(); path = p.chromium.executable_path; p.stop(); \
	    import pathlib; print('✅ Chromium at', path) \
	    if pathlib.Path(path).exists() else print('❌ Chromium binary missing – run: make install-playwright')"

# ── VPS Service ───────────────────────────────────────────────────────────────

restart:
	systemctl restart pdf-app
	systemctl is-active pdf-app

stop:
	systemctl stop pdf-app

status:
	systemctl status pdf-app

logs:
	journalctl -u pdf-app -f

logs-100:
	journalctl -u pdf-app -n 100

logs-nginx:
	tail -f /var/log/nginx/access.log

# ── Build & Deploy ────────────────────────────────────────────────────────────

build:
	uv build

push:
	git push

deploy: push restart

# ── Maintenance ───────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

db-stats:
	@sqlite3 data/ocr_cache.db \
	    "SELECT COUNT(*) as entries, \
	            ROUND(SUM(LENGTH(ocr_text))/1024.0/1024.0, 2) as text_mb, \
	            SUM(input_tokens+output_tokens) as total_tokens_saved \
	     FROM ocr_cache;" 2>/dev/null \
	|| echo "No cache database found (data/ocr_cache.db)"

db-clear:
	rm -f data/ocr_cache.db
	@echo "Cache cleared – next OCR run will re-process all pages."
