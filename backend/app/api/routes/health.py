from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.db.database import engine

router = APIRouter()

@router.get("/health")
def health_check():
	try:
		with engine.connect() as connection:
			connection.execute(text("SELECT 1"))
		return {
			"status":"healthy",
			"database":"connected"
		}
	except SQLAlchemyError:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail={
				"status":"unhealthy",
				"database":"disconnected"
			}
		)