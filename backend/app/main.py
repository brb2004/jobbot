from fastapi import FastAPI
from app.api.routes import preferences_routes, auth_routes, jobs_routes, matches_routes, resumes_routes

app = FastAPI()
app.include_router(preferences_routes.router)
app.include_router(auth_routes.router)
app.include_router(jobs_routes.router)
app.include_router(matches_routes.router)
app.include_router(resumes_routes.router)