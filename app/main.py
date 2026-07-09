from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict

from app.database import init_db, save_result, get_history
from app.safety import score_text

app = FastAPI(title="AI Safety Toolkit")


class ScoreRequest(BaseModel):
    text: str


@app.on_event("startup")
async def startup_event():
    init_db()


@app.post("/score")
async def score_text_endpoint(request: ScoreRequest) -> Dict:
    scores = score_text(request.text)
    record = {
        "text": request.text,
        "toxicity": scores["toxicity"],
        "bias": scores["bias"],
        "disallowed": scores["disallowed"],
        "overall_score": scores["overall_score"],
        "label": scores["label"],
    }
    save_result(record)
    return record


@app.get("/history")
async def history_endpoint():
    return get_history()
