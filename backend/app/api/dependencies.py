from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.db.database import get_db
from backend.app.db.models import User

def get_current_user(
		authorization: str|None= Header(default=None),
		db:Session=Depends(get_db)
)->User:
	unauthorised = HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Invalid or missing authentication token",
		headers={"WWW-Authenticate":"Bearer"}
	)

	if authorization is None:
		raise unauthorised

	scheme,_,token = authorization.partition(" ")

	if scheme.lower()!="bearer" or not token:
		raise unauthorised
	try:
		user_id = decode_access_token(token)
	except Exception:
		raise unauthorised

	user = db.query(User).filter(User.id == user_id).first()

	if user is None or not user.is_active:
		raise unauthorised

	return user

