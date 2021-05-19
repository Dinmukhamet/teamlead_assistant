from .base import BaseModel, TimedBaseModel, db


class Kata(BaseModel):
    __tablename__ = "katas"

    id = db.Column(db.String, primary_key=True, unique=True)
    name = db.Column(db.String)
    slug = db.Column(db.String)


class SolvedKata(BaseModel):
    __tablename__ = "solved_katas"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    kata_id = db.Column(db.String, db.ForeignKey('katas.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.tg_id'))
