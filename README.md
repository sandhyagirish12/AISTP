# AI Safety Toolkit for Open-Weight Models

A lightweight prototype for scoring and monitoring text outputs from open-weight models.

## Components

- `app/main.py`: FastAPI backend with `/score` and `/history` endpoints.
- `app/safety.py`: Risk scoring logic for toxicity, bias, and disallowed content.
- `app/database.py`: SQLite persistence for scored outputs.
- `dashboard/app.py`: Streamlit dashboard for text submission and results.

## Installation

1. Create a Python virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run

1. Start the backend:
   ```bash
   uvicorn app.main:app --reload
   ```
2. In another terminal, start the Streamlit dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```
## Image safety assessment

- Upload an AI-generated image in the dashboard.
- The backend evaluates the image with a prototype visual-risk heuristic.
- Results include graphic sensitivity, violence risk, and NSFW risk scores.
## Notes

- The backend stores scored outputs in `app/safety_history.db`.
- The project is built as a minimal proof-of-concept for open-weight model safeguards.
