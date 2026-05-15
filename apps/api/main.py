from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.api.v1 import eval_runs, task_runs, traces


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="BrowseComp Eval API", version="1.0.0", lifespan=lifespan)

app.include_router(eval_runs.router, prefix="/v1", tags=["eval-runs"])
app.include_router(task_runs.router, prefix="/v1", tags=["task-runs"])
app.include_router(traces.router, prefix="/v1", tags=["traces"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
