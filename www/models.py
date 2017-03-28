# -*- coding: UTF-8 -*-
import time
import uuid
from orm import (
    Model, StringField, BooleanField, TextField, IntegerField
    )


def next_id():
    return '%s%s' % (int(time.time()), uuid.uuid1().hex)


class User(Model):
    __table_name__ = 'user'
    id = StringField(primary_key=True, default=next_id(), ddl='varchar(50)')
    password = StringField(ddl='varchar(50)')
    is_admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    created_at = StringField(
        default=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    )


class Blog(Model):
    __table_name__ = 'blog'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    title = StringField(ddl='varchar(50)')
    title_en = StringField(ddl='varchar(50)')  # english title for url
    summary = StringField(ddl='varchar(200)')
    categery_id = IntegerField()
    content = TextField()
    created_at = StringField(
        default=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    )


class Categery(Model):
    __table_name__ = 'categery'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    name = StringField(ddl='varchar(50)')


class Tag(Model):
    __table_name__ = 'tag'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    name = StringField(ddl='varchar(50)')
    blog_id = IntegerField()
