from peewee import *
from datetime import datetime

db = SqliteDatabase('db/taxi.db')

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    user_id = IntegerField(unique=True)
    phone = CharField()
    role = CharField()  # 'driver' или 'passenger'
    language = CharField(default='ru')
    is_approved = BooleanField(default=False)

class Car(BaseModel):
    owner = ForeignKeyField(User, backref='cars')
    brand = CharField()
    model = CharField()
    year = IntegerField()

class Order(BaseModel):
    creator = ForeignKeyField(User, backref='orders')
    departure_lat = FloatField()
    departure_lon = FloatField()
    destination = CharField()
    departure_time = DateTimeField()
    is_urgent = BooleanField(default=False)
    seats = IntegerField()
    preferred_brand = CharField(null=True)
    channel_message_id = IntegerField(null=True)
    created_at = DateTimeField(default=datetime.now)

db.connect()
db.create_tables([User, Car, Order])eferred_brand = CharField(null=True)  # Предпочтительная марка
    channel_message_id = IntegerField(null=True)  # ID сообщения в канале
    created_at = DateTimeField(default=datetime.now)

db.connect()
db.create_tables([User, Car, Order])