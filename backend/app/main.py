from fastapi import FastAPI

app = FastAPI(title="Conversational Data API")

@app.get("/")
def hello():
	return {
		"message":"hello there"
	}