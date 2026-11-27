import re
from pathlib import Path
from backend.app.core.config import settings
from backend.app.db.models import Dataset

_STORED_FILENAME_PATTERN=re.compile(r"[0-9a-f]{32}\.csv")

class DatasetFileError(Exception):
	pass

def get_dataset_path(dataset:Dataset)->Path:
	filename=dataset.stored_filename
	if not _STORED_FILENAME_PATTERN.fullmatch(filename):
		raise DatasetFileError("Dataset has an invalid stored filename.")
	storage_dir=Path(settings.storage_dir).resolve()
	path=(storage_dir/filename).resolve()
	if path.parent!=storage_dir or not path.is_file():
		raise DatasetFileError("Dataset file was not found.")
	return path

