"""FastAPI boundary for submitting and observing crawl runs."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import AnyHttpUrl, BaseModel, ConfigDict

from .orchestrator import Pipeline, RunSummary


class SubmitRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: AnyHttpUrl


def create_app(pipeline: Pipeline) -> FastAPI:
    app = FastAPI(title="Broadcast Metadata Automation", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/runs", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
    def submit_run(request: SubmitRun) -> RunSummary:
        return pipeline.submit(str(request.url))

    @app.get("/runs/{run_id}", response_model=RunSummary)
    def get_run(run_id: UUID) -> RunSummary:
        summary = pipeline.get(run_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="crawl run not found")
        return summary

    return app
