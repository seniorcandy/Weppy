# -*- coding: UTF-8 -*-
"""
Encapsulate the SQL to protect the server from injection
"""
import asyncio
import logging
import aiomysql


def log(sql, args=()):
    logging.info('SQL: %s' % sql)


@asyncio.coroutine
def create_pool(loop, **kargs):
    logging.info('creating database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kargs.get('host', 'localhost'),
        port=kargs.get('port', 8800),
        user=kargs['user'],
        password=kargs['password'],
        db=kargs['db'],
        charset=kargs.get('charset', 'utf8'),
        autocommit=kargs.get('autocommit', True),
        maxsize=kargs('maxsize', 10),
        minsize=kargs('minsize', 1),
        loop=loop
    )


@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with (yield from __pool) as connection:
        cursor = yield from connection.cursor(aiomysql.DictCursor)
        yield from cursor.execute(sql.replace('?', '%s'), args or ())

        # use size parameter implement limit of result size
        if size:
            result = yield from cursor.fetchmany(size)
        else:
            result = yield from cursor.fetchall()
        yield from cursor.close()
        logging.info('rows returned: %s' % len(result))
        return result


@asyncio.coroutine
def execute(sql, args):
    # excute insert, update, delete
    log(sql)
    with (yield from __pool) as connection:
        try:
            cursor = yield from connection.cursor()
            yield from cursor.execute(sql.replace('?', '%s'), args)
            affected = cursor.rowcount
            yield from cursor.close()
        except BaseException as e:
            log(e)
            raise
        return affected


def create_args_string(length):
    lst = []
    for n in range(length):
        lst.append('?')
    return ', '.join(lst)


class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__, self.column_type, self.name)

    def __repr__(self):
        return '%s: %s' % (self.name, self.default)


class StringField(Field):
    def __init__(
        self, name=None, primary_key=False, default=None, ddl='varchar(100)'
    ):
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super.__init__(name, 'boolean', False, default)

    def __str__(self):
        return '<%s, %s:%s>' % (
            self.__class__, self.column_type, self.name
            )

    def __repr__(self):
        return '%s: %s' % (self.name, self.default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

    def __str__(self):
        return '<%s, %s:%s>' % (
            self.__class__, self.column_type, self.name
            )

    def __repr__(self):
        return '%s: %s' % (self.name, self.default)


class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


class ModelMetaClass(type):
    # This metaclass will be used when creating model
    def __new__(cls, name, parents, attrs):
        if name == "Modele":
            return type.__new__(cls, name, parents, attrs)

        table_name = attrs.get("__table_name__", None) or name
        logging.info("found model: %s (table %s)" % (name, table_name))
        mappings = dict()  # store attributes' name and values
        fields = []  # attributes' name
        primary_key = None
        for key, value in attrs.items():
            if isinstance(value, Field):
                logging.info("found mapping: %s ==> %s" % (key, value))
                mappings[key] = value
                if value.primary_key:
                    if primary_key:
                        raise Exception(
                            'Duplicate primary key for field: %s' % key
                        )
                    primary_key = key
                else:
                    fields.append(key)
        if not primary_key:
            raise Exception("Primary key is not found")
        for key in mappings.keys():
            attrs.pop(key)
        escaped_fields = list(map(lambda f: "`%s`" % f, fields))
        attrs['__mappings__'] = mappings
        attrs['__table_name__'] = table_name
        attrs['__primary_key__'] = primary_key
        attrs['__fields__'] = fields
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (
            primary_key, ', '.join(escaped_fields), table_name
        )
        attrs['__insert__'] = 'insert into  `%s` (%s, `%s`) values(%s)' % (
            table_name, ', '.join(escaped_fields),
            primary_key,
            create_args_string(len(escaped_fields) + 1)
        )
        attrs['__update__'] = 'update `%s` set `%s` where `%s` = ?' % (
            table_name,
            ', '.join(map(lambda f: '`%s` = ?' % (
                mappings.get(f).name or f), fields)
                ),
            primary_key
            )
        attrs['__delete__'] = 'delete from  `%s` where `%s`=?' % (
            table_name,
            primary_key
        )
        return type.__new__(cls, name, parents, attrs)


class Model(dict, metaclass=ModelMetaClass):
    def __init__(self, **kwargs):
        super(Model, self).__init__(**kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                "'Model' object has no attribute: %s" % key
            )

    def __setattr__(self, key, value):
        self[key] = value

    """The getValue() function takes an optional default value,
    which is used if the attribute doesn’t exist"""
    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        # if value is not exit, get the default and value = default
        value = getattr(self, key, None)
        if not value:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(
                    field.default
                ) else field.default
        logging.debug(
            'using default value for %s: %s' % (key, str(value))
        )
        setattr(self, key, value)
        return value

    @classmethod
    @asyncio.coroutine
    def find_all(cls, where=None, args=None, **kwargs):
        sql = [cls.__select__]
        order_by = kwargs.get('order_by', None)
        limit = kwargs.get('limit', None)
        if where:
            sql.append['where']
            sql.append[where]
        if args is None:
            args = []
        if order_by:
            sql.append('order_by')
            sql.append(order_by)
        if limit:
            sql.append['limit']
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError(
                    'Invalid limit value : %s ' % str(limit)
                )
        results = yield from select(' '.join(sql), args)
        return [cls(**r) for r in results]

    @classmethod
    @asyncio.coroutine
    def get_count(cls, select_field, where=None, args=None):
        # select count(*)
        sql = [
            'select %s __num__ from `%s`' % (select_field, cls.__table_name__)
        ]
        if where:
            sql.append('where')
            sql.append(where)
            size = 1
            results = yield from select(' '.join(sql), args, size)
            if len(results) == 0:
                return None
            return results[0]['__num__']

    @classmethod
    @asyncio.coroutine
    def find(cls, primary_key):
        '''find object by primary key'''
        size = 1
        results = yield from select(
            '%s where `%s`=?' % (cls.__select__, cls.__primary_key__),
            [primary_key],
            size
        )
        if len(results) == 0:
            return None
        return cls(**results[0])

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__updata__, args)
        if rows != 1:
            logging.warn(
                'failed to update by primary key: affected rows: %s' % rows
            )

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__updata__, args)
        if rows != 1:
            logging.warn(
                'failed to remove by primary key: affected rows: %s' % rows
            )
