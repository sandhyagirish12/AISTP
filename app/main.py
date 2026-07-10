from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Dict

from app.database import init_db, save_result, get_history, save_image_result, get_image_history
from app.safety import score_text, score_image_bytes, score_video_bytes

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


@app.post("/score-image")
async def score_image_endpoint(file: UploadFile = File(...)) -> Dict:
    file_bytes = await file.read()
    try:
        scores = score_image_bytes(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    record = {
        "filename": file.filename,
        "graphic": scores["graphic"],
        "violence": scores["violence"],
        "nsfw": scores["nsfw"],
        "overall_score": scores["overall_score"],
        "label": scores["label"],
    }
    save_image_result(record)
    return scores


@app.get("/history-images")
async def history_images_endpoint():
    return get_image_history()


@app.post("/score-video")
async def score_video_endpoint(file: UploadFile = File(...)) -> Dict:
    file_bytes = await file.read()
    try:
        scores = score_video_bytes(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return scores
