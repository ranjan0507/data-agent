from fastapi import FastAPI
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.dataset import router as dataset_router
from backend.app.api.routes.conversation import router as conversation_router

app = FastAPI(title="Conversational Data API")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dataset_router)
app.include_router(conversation_router)

@app.get("/")
def hello():
	return {
		"message":"Backend is running"
	}
