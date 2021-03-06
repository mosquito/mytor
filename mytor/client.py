# encoding: utf-8
from multiprocessing import RLock
from tornado.ioloop import IOLoop
from tornado.gen import Future
from .util import async_call_method
from .connections import Connection
from .cursor import Cursor


class Client(object):
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._connection = None
        self._closed = False
        self._close_callback = None
        self._io_loop = kwargs.pop('io_loop', None)

        self.__cursor_lock = RLock()

        if self._io_loop is None:
            self._io_loop = IOLoop.current()

        if "cursorclass" in kwargs and issubclass(kwargs["cursorclass"], Cursor):
            kwargs["cursorclass"] = kwargs["cursorclass"].__delegate_class__

    def connect(self):
        future = Future()

        def on_connect(connection_future):
            if connection_future._exc_info is None:
                self._connection = connection_future._result
                self._connection.set_close_callback(self.on_close)
                future.set_result(self)
            else:
                future.set_exc_info(connection_future._exc_info)

        connection_future = async_call_method(Connection, *self._args, **self._kwargs)

        IOLoop.current().add_future(connection_future, on_connect)
        return future

    def on_close(self):
        self._closed = True

        if self._close_callback and callable(self._close_callback):
            self._close_callback(self)

        self._close_callback = None

    def set_close_callback(self, callback):
        self._close_callback = callback

    def close(self):
        if self._closed:
            return
        return async_call_method(self._connection.close)

    def autocommit(self, value):
        return async_call_method(self._connection.autocommit, value)

    def begin(self):
        return async_call_method(self._connection.begin)

    def commit(self):
        return async_call_method(self._connection.commit)

    def rollback(self):
        return async_call_method(self._connection.rollback)

    def show_warnings(self):
        return async_call_method(self._connection.show_warnings)

    def select_db(self, db):
        return async_call_method(self._connection.select_db, db)

    def cursor(self, cursor_cls=None):
        if cursor_cls is None:
            cursor_cls = self._connection.cursorclass

        if not self.__cursor_lock.acquire(0):
            raise RuntimeError("Connection might provide only one opened cursor")

        if cursor_cls and issubclass(cursor_cls, Cursor):
            original_cursor_cls = cursor_cls.__delegate_class__
        else:
            original_cursor_cls = cursor_cls

        cursor = self._connection.cursor(original_cursor_cls)
        cursor_cls = cursor_cls if issubclass(cursor_cls, Cursor) else cursor.__mytor_class__

        cursor = cursor_cls(cursor)
        cursor._release_lock = lambda *a: self.__cursor_lock.release()
        return cursor

    def query(self, sql, unbuffered=False):
        return async_call_method(self._connection.query, sql, unbuffered)

    def next_result(self):
        return async_call_method(self._connection.next_result)

    def kill(self, thread_id):
        return async_call_method(self._connection.kill, thread_id)

    def ping(self, reconnect=True):
        return async_call_method(self._connection.ping, reconnect)

    def set_charset(self, charset):
        return async_call_method(self._connection.set_charset, charset)

    def __getattr__(self, name):
        return getattr(self._connection, name)
