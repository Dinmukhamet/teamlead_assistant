from sqlalchemy.sql import expression
from .base import TimedBaseModel, db


class User(TimedBaseModel):
    __tablename__ = "users"

    tg_id = db.Column(db.Integer, primary_key=True, unique=True)
    tg_username = db.Column(db.String(50), nullable=True)
    cw_username = db.Column(db.String(50))
    is_mentor = db.Column(db.Boolean(), default=False, nullable=True)


class MenteeToMentor(TimedBaseModel):
    __tablename__ = "pairs"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.tg_id'))
    mentee_id = db.Column(db.Integer, db.ForeignKey('users.tg_id'))


class Feedback(TimedBaseModel):
    __tablename__ = "feedbacks"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.tg_id'))
    mentee_id = db.Column(db.Integer, db.ForeignKey('users.tg_id'))
    rate = db.Column(db.Integer)
