from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.conversation import (
	ConversationResponse,
	MessageCreate,
	MessageResponse
)
from backend.app.services import conversation_services, dataset_service

router = APIRouter(tags=["conversations"])

def require_owned_conversation(db:Session,*,conversation_id:int,owner_id:int):
	conversation=conversation_services.get_owned_conversation(
		db,
		conversation_id=conversation_id,
		owner_id=owner_id
	)
	if conversation is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Conversation not found.")
	return conversation

@router.post("/datasets/{dataset_id}/conversations",response_model=ConversationResponse,status_code=201)
def create_conversation(
	dataset_id:int,
	db:Session=Depends(get_db),
	current_user:User=Depends(get_current_user)
):
	dataset=dataset_service.get_owned_dataset(db,dataset_id=dataset_id,owner_id=current_user.id)
	if dataset is None:
		raise HTTPException(status_code=404,detail="Dataset not found.")
	return conversation_services.create_conversation(db,dataset_id=dataset.id)

@router.get("/datasets/{dataset_id}/conversations",response_model=list[ConversationResponse])
def list_conversations(
	dataset_id:int,
	db:Session=Depends(get_db),
	current_user:User=Depends(get_current_user)
):
	dataset=dataset_service.get_owned_dataset(db,dataset_id=dataset_id,owner_id=current_user.id)
	if dataset is None:
		raise HTTPException(status_code=404,detail="Dataset not found.")
	return conversation_services.list_conversations(db,dataset_id=dataset.id)

@router.get("/conversations/{conversation_id}",response_model=ConversationResponse)
def get_conversation(
	conversation_id:int,
	db:Session=Depends(get_db),
	current_user:User=Depends(get_current_user)
):
	return require_owned_conversation(
		db,conversation_id=conversation_id,owner_id=current_user.id
	)

@router.post("/conversation/{conversation_id}/messages",response_model=MessageResponse,status_code=201)
def create_message(
	conversation_id:int,
	payload:MessageCreate,
	db:Session=Depends(get_db),
	current_user:User=Depends(get_current_user)
):
	conversation=require_owned_conversation(
		db,conversation_id=conversation_id,owner_id=current_user.id
	)
	return conversation_services.create_message(
		db,
		conversation_id=conversation.id,
		role=payload.role,
		content=payload.content
	)


@router.get("/conversations/{conversation_id}/messages",response_model=list[MessageResponse])
def list_messages(
	conversation_id:int,
	db:Session=Depends(get_db),
	current_user:User=Depends(get_current_user)
):
	conversation=require_owned_conversation(
		db,conversation_id=conversation_id,owner_id=current_user.id
	)
	return conversation_services.list_messages(db,conversation_id=conversation.id)