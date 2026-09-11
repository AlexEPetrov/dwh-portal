"""DataProvider"""

from typing import List, Optional, Type, TypeVar

import pandas as pd
from pandas import DataFrame
from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from infrastructure.db.session_management import SessionProvider

T = TypeVar("T")


class DataProvider:
    """
    Провайдер для загрузки данных в виде DB моделей (db entity). Используется лдля загрузки смежных данных в рамках
    работы внутри дб репозитория или для единичных обращений к БД (ВНЕ repository pattern)
    """

    def __init__(self, session: Session):
        if session is not None:
            self.session = session
        else:
            self.session = SessionProvider.create_session()

    def all(self, cls: Type[T]) -> List[T]:
        """Возвращает все записи запрашиваемой сущности (таблицы)"""
        found_records = self.session.query(cls).all()
        if len(found_records) > 0:
            return found_records
        # raise ValueError(cls.get_nothing_found_msg(err_msg))
        return []

    def filter(self, cls: Type[T], filter_expression) -> List[T]:
        """Возвращает элементы, соответтвующие условию (или пустая коллекция если нет таких запией)."""
        found_records = self.session.query(cls).filter(filter_expression).all()
        return found_records

    def first(self, cls: Type[T], filter_expression) -> T:
        """Возвращает первый элемент, соответствующий условию. Генерирует Exception если нет таких записей."""
        value = self.first_or_default(cls, filter_expression)
        if value is None:
            raise ValueError(f"Объект не найден ({filter_expression})")
        return value

    def first_or_default(self, cls: Type[T], filter_expression) -> Optional[T]:
        """Возвращает первый элемент, соответствующий условию.
        Возвращает None при отсутсвии элементов в наборе данных"""
        found_record = self.session.query(cls).filter(filter_expression).first()
        return found_record

    def filter_by_max(self, cls: Type[T], max_attr, filter_expr) -> List[T]:
        """Метод нахождения последней ревизии данных"""
        subquery = self.session.query(func.max(max_attr)).filter(filter_expr)
        query = self.session.query(cls).filter(filter_expr, max_attr == subquery)
        return query.all()

    def read_data_frame(self, sql) -> DataFrame:
        """Чтение данных в DataFrame"""
        with self.session.connection() as conn:
            ret_val = pd.read_sql(sql, con=conn)
            return ret_val

    def delete(self, cls: Type[T], filter_expression, auto_commit: bool = True):
        """Удаление записей по условию"""
        statement = delete(cls).where(filter_expression)
        self.session.execute(statement)
        if auto_commit:
            self.session.commit()
