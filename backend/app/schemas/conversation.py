from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

class ConversationResponse(BaseModel):
	id:int
	dataset_id:int
	created_at:datetime
	model_config=ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
	role:Literal["user","assistant"]
	content:str=Field(min_length=1)

class MessageResponse(BaseModel):
	id:int
	conversation_id:int
	role:str
	content:str
	created_at:datetime
	model_config=ConfigDict(from_attributes=True)

