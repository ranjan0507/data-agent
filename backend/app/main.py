from fastapi import FastAPI
from backend.app.api.routes.health import router
app = FastAPI(title="Conversational Data API")

app.include_router(router)

@app.get("/")
def hello():
	return {
		"message":"Backend is running"
	}
