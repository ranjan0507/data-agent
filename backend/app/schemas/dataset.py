from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DatasetResponse(BaseModel):
	id:int
	original_filename:str
	file_size:int
	content_type:str
	created_at: datetime
	model_config=ConfigDict(from_attributes=True)
	