from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.app.core.config import settings

password_hasher = PasswordHasher()

def normalize_email(email:str)->str:
	return email.strip().lower()

def hash_password(password:str)->str:
	return password_hasher.hash(password)

def verify_password(password:str, hashed_password:str)->bool:
	try:
		return password_hasher.verify(hashed_password,password)
	except VerifyMismatchError:
		return False

def create_access_token(user_id:int)->str:
	expires = datetime.now(timezone.utc)+timedelta(
		minutes=settings.access_token_expire_minutes
	)
	payload={
		"sub":str(user_id),
		"exp":expires
	}
	return jwt.encode(
		payload,
		settings.jwt_secret_key,
		algorithm=settings.jwt_algorithm
	)

def decode_access_token(token:str)->int:
	payload=jwt.decode(
		token,
		settings.jwt_secret_key,
		algorithms=[settings.jwt_algorithm]
	)
	subject=payload.get("sub")
	if subject is None:
		raise jwt.InvalidTokenError
	return int(subject)
