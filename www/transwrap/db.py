#!/usr/bin/env python
# -*- coding: utf-8 -*-


'''
Database operation module
'''

import time
import uuid
import functools
import threading
import logging
import collections
import os
import datetime


class Dict(dict):
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value


class DBError(Exception):
    pass


class MultiColumnsError(DBError):
    pass



def next_id(t=None):
    '''
    Return next id as 50-char string.
    Args:
        t: unix timestamp, default to None and using time.time().
    '''

    if t is None:
        t = time.time()
    return '%015d%s000' % (int(t * 1000), uuid.uuid4().hex)


class _LasyConnection(object):

    def __init__(self):
        self.connection = None

    def cursor(self):
        if self.connection is None:
            connection = engine.connect()
            logging.info('open connection <%s>...' % hex(id(connection)))
            self.connection = connection
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def cleanup(self):
        if self.connection:
            connection = self.connection
            logging.info('close connection <%s>...' % hex(id(connection)))
            connection.close()


class _DbCtx(threading.local):
    '''
    Thread local object that holds connection info
    '''

    def __init__(self):
        self.connection = None
        self.transactions = 0

    def is_init(self):
        return not self.connection is None

    def init(self):
        logging.info('open lazy connection...')
        self.connection = _LasyConnection()
        self.transactions = 0

    def cleanup(self):
        self.connection.cleanup()
        self.connection = None

    def cursor(self):
        '''
        Return cursor
        '''
        return self.connection.cursor()

# thread-local db context:
_db_ctx = _DbCtx()

# global engine object:
engine = None


class _Engine(object):

    def __init__(self, connect):
        self._connect = connect  # connect is a anonymous function

    def connect(self):
        return self._connect()  # what's the intension _connect() ?


def create_engine(user, password, database, host='127.0.0.1', port=3306, **kw):
    import mysql.connector
    global engine
    if engine is not None:
        raise DBError('Engine is already initialized.')
    params = dict(user=user, password=password, database=database, host=host, port=port)
    defaults = dict(charset='utf8', collation='utf8_general_ci', autocommit=False)
    for k, v in defaults.iteritems():
        params[k] = kw.pop(k, v)
    params.update(kw)
    params['buffered'] = True
    #  why lamada ?
    engine = _Engine(lambda: mysql.connector.connect(**params))
    # test connection
    logging.info('Init mysql engine <%s> ok.' % hex(id(engine)))


class _ConnectionCtx(object):
    '''
    '''

    def __enter__(self):
        global _db_ctx
        self.should_cleanup = False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_cleanup = True
        return self

    def __exit__(self, exctype, excvalue, traceback):
        global _db_ctx
        if self.should_cleanup:
            _db_ctx.cleanup()


def connection():
    '''
    '''
    return _ConnectionCtx()


def with_connection(func):
    '''
    Decorator for reuse connection

    @with_connection
    def foo(*args, **kw):
        f1()
        f2()
        f3()
    '''
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        with _ConnectionCtx():
            return func(*args, **kw)
    return _wrapper


class _TransactionCtx(object):
    '''
    '''

    def __enter__(self):
        global _db_ctx
        self.should_close_conn = False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_close_conn = True
        _db_ctx.transactions = _db_ctx.transactions + 1
        logging.info('begin transaction...' if _db_ctx.transactions == 1 else 'join current transation...')
        return self

    def __exit(self, exctype, excvalue, traceback):
        global _db_ctx
        _db_ctx.transactions = _db_ctx.transactions - 1
        try:
            if _db_ctx.transactions == 0:
                if exctype is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            if self.should_close_conn:
                _db_ctx.cleanup()

    def commit(self):
        global _db_ctx
        logging.info('commit transaction...')

        try:
            _db_ctx.connection.commit()
            logging.info('commit ok')
        except:
            logging.warning('commit failed. try rollback...')
            _db_ctx.connection.rollback()
            logging.warning('rollback ok')
            raise

    def rollback(self):
        global _db_ctx
        logging.warning('rollback transaction...')
        _db_ctx.connection.rollback()
        logging.info('rollback ok ok ok.')


def transaction():
    '''
    Create a transation object so we can use with statement:

    with transation():
        pass

    '''
    return _TransactionCtx()


def with_transaction(func):
    '''
    A decorator that makes function around transation

    '''

    @functools.wraps(func)
    def _wrapper(*args, **kw):
        # _start = time.time()
        with _TransactionCtx():
            return func(*args, **kw)

        # _profilling(_start)
    return _wrapper


def _select(sql, first, *args):
    'execute select SQL and return unique result or list results.'
    global _db_ctx
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_ctx.connection.cursor()
        cursor.execute(sql, args)
        if cursor.description:
            names = [x[0] for x in cursor.description]
        if first:
            values = cursor.fetchone()
            if not values:
                return None
            return Dict(names, values)
        return [Dict(names, x) for x in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()


@with_connection
def select_one(sql, *args):
    '''
    '''
    return _select(sql, True, *args)


@with_connection
def select_int(sql, *args):
    '''
    Execute select SQL and expected only one int result
    '''
    d = _select(sql, True, *args)
    if len(d) != 1:
        raise MultiColumnsError('Expect only one column')
    return d.values()[0]


@with_connection
def select(sql, *args):
    return _select(sql, False, *args)


@with_connection
def _update(sql, *args):
    global _db_ctx
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_ctx.connection.cursor()  
        cursor.execute(sql, args)
        r = cursor.rowcount
        print _db_ctx.transactions
        if _db_ctx.transactions == 0:
            logging.info('auto commit')
            _db_ctx.connection.commit()
        return r
    finally:
        if cursor:
            cursor.close()


def insert(table, **kw):
    ''' Execute insert SQL
    '''
    cols, args = zip(*kw.iteritems())
    sql = 'insert into `%s` (%s) values (%s)' % (table, ','.join('`%s`' % col for col in cols), ','.join(['?' for i in range(len(cols))]))
    return _update(sql, *args)


def update(sql, *args):
    '''
    '''
    return _update(sql, *args)


# test for doctest
def factorial(n):
    '''
    >>> [factorial(n) for n in range(6)]
    [1, 1, 2, 6, 24, 120]
    '''
    import math
    if not n >= 0:
        raise ValueError('n must be >= 0')
    if math.floor(n) != n:
        raise ValueError('n must be exact integer')
    if n+1 == n:  # catch a value like 1e300
        raise OverflowError('n too large')
    result = 1
    factor = 2
    while factor <= n:
        result *= factor
        factor += 1
    return result

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    create_engine('root', 'admin', 'awesome_webapp')
    update('drop table if exists user_tb')
    update('create table user_tb (id int primary key, name text, email text, passwd text, last_modified real)')
    # doctest 作用：查找注释中命令行格式的代码片段，执行验证是否符合预期
    # 没有输出是ok的，也可以python xx.py -v 查看
    import doctest
    doctest.testmod()





