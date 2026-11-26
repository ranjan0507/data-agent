from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, ForeignKey,Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base

class User(Base):
	__tablename__="users"

	id: Mapped[int] = mapped_column(primary_key=True)
	email: Mapped[str] = mapped_column(
		String(320),
		unique= True,
		index=True,
		nullable=False
	)
	hashed_password: Mapped[str] = mapped_column(
		String(255),
		nullable=False
	)
	is_active: Mapped[bool] = mapped_column(
		Boolean,
		default=True,
		nullable=False
	)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		nullable=False
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False
	)

class Dataset(Base):
	__tablename__="datasets"

	id: Mapped[int]=mapped_column(primary_key=True)
	owner_id:Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
	original_filename:Mapped[str]=mapped_column(String(255),nullable=False)
	stored_filename:Mapped[str]=mapped_column(String(255),nullable=False,unique=True)
	file_size:Mapped[int]=mapped_column(nullable=False)
	content_type:Mapped[str]=mapped_column(String(100),nullable=False)
	created_at: Mapped[datetime]=mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		nullable=False
	)

class Conversation(Base):
	__tablename__="conversations"
	id:Mapped[int]=mapped_column(primary_key=True)
	dataset_id:Mapped[int] = mapped_column(
		ForeignKey("datasets.id",ondelete="CASCADE"),
		nullable=False,
		index=True
	)
	created_at:Mapped[datetime]=mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		nullable=False
	)

class Message(Base):
	__tablename__="messages"
	id:Mapped[int]=mapped_column(primary_key=True)
	conversation_id:Mapped[int]=mapped_column(
		ForeignKey("conversations.id",ondelete="CASCADE"),
		nullable=True,
		index=True
	)
	role:Mapped[str]=mapped_column(String(20),nullable=False)
	content:Mapped[str]=mapped_column(Text,nullable=False)
	created_at:Mapped[datetime]=mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		nullable=False
	)