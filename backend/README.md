# NauDisha — Backend Service

The Python FastAPI backend service for the **NauDisha Dynamic Maritime Navigation and Route Optimization Platform**.

---

## 1. Quick Start

### Prerequisites
* Python 3.10+
* Virtual environment (`venv`)

### Installation
From the `backend/` directory:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Running the Development Server
```bash
python -m uvicorn naudisha.api.main:app --host 0.0.0.0 --port 8000 --reload
```

* **Interactive API Documentation (Swagger):** `http://localhost:8000/docs`
* **Alternative API Docs (ReDoc):** `http://localhost:8000/redoc`
* **Health Probe:** `http://localhost:8000/health`

---

## 2. Environment Variables

Copy `.env.example` to `.env` in the `backend/` or root directory:
```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `HOST` | Bind host address | `0.0.0.0` |
| `PORT` | Bind port number | `8000` |
| `COPERNICUS_MARINE_USERNAME` | Copernicus Marine account username (Optional) | |
| `COPERNICUS_MARINE_PASSWORD` | Copernicus Marine account password (Optional) | |
| `AISSTREAM_API_KEY` | AISStream.io live AIS satellite stream key (Optional) | |

---

## 3. Running Automated Tests

Run the complete deterministic unit test suite from `backend/`:
```bash
python -m unittest discover -s tests
```
Or from the project root:
```bash
python -m unittest discover -s backend/tests
```
