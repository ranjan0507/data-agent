import logging
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.dataset import DatasetResponse
from backend.app.services import dataset_service, storage_services
from backend.app.services.storage_services import FileTooLargeError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets",tags=["datasets"])

@router.post("",response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def upload_dataset(
	file:UploadFile=File(...),
	db:Session=Depends(get_db),
	current_user: User=Depends(get_current_user)
):
	try:
		stored_filename,original_filename,file_size=storage_services.save_csv(file)
	except FileTooLargeError as exc:
		raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE,detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(exc)) from exc

	try:
		return dataset_service.create_dataset(
			db,
			owner_id=current_user.id,
			orignal_filename=original_filename,
			stored_filename=stored_filename,
			file_size=file_size,
			content_type=file.content_type or "text/csv"
		)
	except SQLAlchemyError as exc:
		db.rollback()
		try:
			storage_services.delete_csv(storage_services)
		except OSError:
			logger.exception("Failed to remove uploaded CSV after database failure")
		logger.exception("Failed to save dataset metadata")
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Could not save dataset metadata."
		) from exc

@router.get("",response_model=list[DatasetResponse])
def get_datasets(db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
	return dataset_service.list_datasets(db,current_user.id)

@router.get("/{dataset_id}",response_model=DatasetResponse)
def get_dataset(dataset_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
	dataset=dataset_service.get_owned_dataset(
		db,dataset_id=dataset_id,owner_id=current_user.id
	)
	if dataset is None:
		raise HTTPException(status_code=404,detail="Dataset not found.")
	return dataset

@router.delete("/{dataset_id}",status_code=status.HTTP_204_NO_CONTENT)
def remove_dataset(dataset_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
	dataset=dataset_service.get_owned_dataset(db,dataset_id=dataset.id,owner_id=current_user.id)
	if dataset is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Dataset not found.")
	stored_filename=dataset_service.delete_dataset(db,dataset)
	try:
		storage_services.delete_csv(stored_filename)
	except OSError as exc:
		logger.exception("Failed to remove deleted dataset file")
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
		                    detail="Dataset metadata was deleted, but its file could not be removed.") from exc

	return Response(status_code=status.HTTP_204_NO_CONTENT)
