from fastapi import FastAPI

app = FastAPI(title="Yosubi Voice Companion")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
