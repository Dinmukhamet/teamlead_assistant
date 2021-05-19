from sqlalchemy.sql import expression
from .base import TimedBaseModel, db


class Chat(TimedBaseModel):
    __tablename__ = "chats"

    id = db.Column(db.BigInteger, primary_key=True, index=True)
    chat_type = db.Column(db.String)

    language = db.Column(db.String(12), default="en")
    join_filter = db.Column(db.Boolean, server_default=expression.false())