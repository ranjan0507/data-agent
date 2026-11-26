import csv
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from backend.app.core.config import settings

MAX_UPLOAD_SIZE=50*1024*1024
CHUNK_SIZE=1024*1024

class FileTooLargeError(Exception):
	pass

def _dataset_directory()->Path:
	directory=Path(settings.storage_dir)
	directory.mkdir(parents=True,exist_ok=True)
	return directory

def _original_filename(filename:str|None)->str:
	name=(filename or "").replace("\\","/").rsplit("/",1)[-1]
	if not name or len(name)>255 or Path(name).suffix().lower()!=".csv":
		raise ValueError("Upload a CSV file with a filename no longer than 255 characters.")
	return name

def _validate_csv(path:Path)->None:
	try:
		with path.open("r",encoding="utf-8-sig",newline="") as source:
			reader=csv.reader(source,strict=True)
			header=next(reader,None)
			if not header or any(not column.strip() for column in header):
				raise ValueError("CSV must have a non-empty header row.")
			for row in reader:
				if len(row)!=len(header):
					raise ValueError("CSV rows must have the same number of columns as the header.")
	except (UnicodeDecodeError,csv.Error) as exc:
		raise ValueError("File is not a valid UTF-8 CSV.")

def save_csv(upload:UploadFile)-> tuple[str,str,int]:
	original_filename=_original_filename(upload.filename)
	directory=_dataset_directory()
	stored_filename=f"{uuid.uuid4().hex}.csv"
	temporary_path=directory/f"{uuid.uuid4().hex}.tmp"
	final_path=directory/stored_filename
	total_size=0

	try:
		with temporary_path.open("wb") as destination:
			while chunk:=upload.file.read(CHUNK_SIZE):
				total_size+=len(chunk)
				if total_size>MAX_UPLOAD_SIZE:
					raise FileTooLargeError
				destination.write(chunk)
		if total_size==0:
			raise ValueError("CSV file is empty.")
		_validate_csv(temporary_path)
		temporary_path.replace(final_path)
	except Exception:
		temporary_path.unlink(missing_ok=True)
		raise

	return stored_filename,original_filename,total_size

def delete_csv(stored_filename:str)->None:
	if not re.fullmatch(r"[0-9a-f]{32}\.csv",stored_filename):
		raise ValueError("Invalid stored filename.")
	(_dataset_directory()/stored_filename).unlink(missing_ok=True)
				