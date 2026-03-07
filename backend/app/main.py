from fastapi import FastAPI
from app.router import router

app = FastAPI(title="LegaLens API")

app.include_router(router)

@app.get("/")
def root():
    return {"message": "LegaLens API"}

