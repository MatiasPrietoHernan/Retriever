from fastapi import FastAPI
from routes.route import router

app = FastAPI(title="HogarFe Hybrid Search API")

app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
