from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.models import Conversation, Dataset, Message

def create_conversation(db:Session,*,dataset_id:int)->Conversation:
	conversation=Conversation(dataset_id=dataset_id)
	db.add(conversation)
	db.commit()
	db.refresh(conversation)
	return conversation

def list_conversations(db:Session,*,dataset_id:int)->list[Conversation]:
	return list(
		db.scalars(select(Conversation).where(Conversation.dataset_id==dataset_id).order_by(Conversation.id))
	)

def get_owned_conversation(db:Session,*,conversation_id:int,owner_id:int)->Conversation|None:
	return db.scalar(
		select(Conversation).join(Dataset,Conversation.dataset_id==Dataset.id)
		.where(Conversation.id==conversation_id,Dataset.owner_id==owner_id)
	)

def create_message(db:Session,*,conversation_id:int,role:str,content:str)->Message:
	message=Message(
		conversation_id=conversation_id,
		role=role,
		content=content
	)
	db.add(message)
	db.commit()
	db.refresh(message)
	return message

def list_messages(db:Session,*,conversation_id:int)->list[Message]:
	return list(
		db.scalars(select(Message).where(Message.conversation_id==conversation_id).order_by(Message.id))
	)