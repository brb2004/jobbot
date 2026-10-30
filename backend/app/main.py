from fastapi import FastAPI
from app.api.routes import jobs_routes, matches_routes

app = FastAPI()
app.include_router(jobs_routes.router)
app.include_router(matches_routes.router)