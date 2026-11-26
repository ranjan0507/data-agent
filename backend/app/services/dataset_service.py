from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Dataset

def create_dataset(
		db:Session,*, 
		owner_id:int,orignal_filename:str,stored_filename:str,
		file_size:int,content_type:str
)->Dataset:
	dataset=Dataset(
		owner_id=owner_id,
		orignal_filename=orignal_filename,
		stored_filename=stored_filename,
		file_size=file_size,
		content_type=content_type
	)
	db.add(dataset)
	db.commit()
	db.refresh(dataset)
	return dataset

def list_datasets(db:Session,owner_id:int)->list[Dataset]:
	return list(
		db.scalars(select(Dataset).where(Dataset.owner_id==owner_id).order_by(Dataset.id))
	)

def get_owned_dataset(
		db:Session,
		*, dataset_id:int, owner_id:int
)->Dataset|None:
	return db.scalar(select(Dataset).where(Dataset.id==dataset_id,Dataset.owner_id==owner_id))

def delete_dataset(db:Session, dataset:Dataset)->str:
	stored_filename=dataset.stored_filename
	db.delete(dataset)
	db.commit()
	return stored_filename

