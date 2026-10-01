"""Adapt the project's small SQLite SQL subset to MySQL transactions."""

import re

import pymysql

from .document_store import connect_mysql
from .document_store import StorageError


class Result:
    def __init__(self, cursor):
        self.rowcount = cursor.rowcount
        self.rows = list(cursor.fetchall()) if cursor.description else []

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows


class MySQLConnection:
    def __init__(self, dict_rows=False):
        self.connection = connect_mysql(dict_rows=dict_rows)

    def ping(self):
        # A transaction must never silently reconnect and lose pending writes.
        self.connection.ping(reconnect=False)

    def execute(self, sql, params=()):
        sql = sql.replace("INSERT OR REPLACE", "REPLACE").replace("?", "%s")
        sql = re.sub(r"\bkey\b", "`key`", sql)
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                return Result(cursor)
        except pymysql.MySQLError as exc:
            raise StorageError("MySQL transaction failed") from exc

    def commit(self):
        try:
            self.connection.commit()
        except pymysql.MySQLError as exc:
            raise StorageError("MySQL commit failed") from exc

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
