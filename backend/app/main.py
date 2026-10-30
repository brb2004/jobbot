from fastapi import FastAPI
from app.api.routes import jobs

app = FastAPI()
app.include_router(jobs.router)