from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.security import (
	create_access_token,
	hash_password,
	normalize_email,
	verify_password
)

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.auth import (
	LoginRequest,
	TokenResponse,
	UserCreate,
	UserResponse
)

router = APIRouter(prefix="/auth",tags=["authentication"])

@router.post("/register",response_model=UserResponse,status_code=201)
def register_user(payload:UserCreate, db:Session=Depends(get_db)):
	email=normalize_email(str(payload.email))
	existing_user=db.query(User).filter(User.email==email).first()

	if existing_user is not None:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="An account with this email already exists"
		)

	user = User(
		email=email,
		hashed_password=hash_password(payload.password)
	)

	db.add(user)
	db.commit()
	db.refresh(user)

	return user


@router.post("/login", response_model=TokenResponse)
def login(payload:LoginRequest, db: Session=Depends(get_db)):
	email = normalize_email(str(payload.email))
	user=db.query(User).filter(User.email==email).first()

	if (user is None or not user.is_active or not verify_password(payload.password,user.hashed_password)):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Incorrect email or password",
			headers={"WWW-Authenticate":"Bearer"}
		)
	return TokenResponse(access_token=create_access_token(user.id))

@router.get("/me",response_model=UserResponse)
def get_me(current_user:User=Depends(get_current_user)):
	return current_user