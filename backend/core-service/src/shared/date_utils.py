import datetime
from typing import Generator, List, Tuple

from dateutil import relativedelta


def get_quarter_first_day(date: datetime.date):
    """Возвращает дату начала квартала по дате"""
    quarter_idx = (date.month - 1) // 3
    if quarter_idx == 0:
        return datetime.date(year=date.year, month=1, day=1)
    if quarter_idx == 1:
        return datetime.date(year=date.year, month=4, day=1)
    if quarter_idx == 2:
        return datetime.date(year=date.year, month=7, day=1)
    if quarter_idx == 3:
        return datetime.date(year=date.year, month=10, day=1)
    raise ValueError("Невозможно определить квартал по дате")


def is_month_last_day(date: datetime.date):
    """True если последний день месяца"""
    tomorrow = date + datetime.timedelta(days=1)
    return tomorrow.month > date.month


def get_next_month(current_month: datetime.date) -> datetime.date:
    return current_month + relativedelta.relativedelta(months=1)


def last_day_of_month(date):
    return (
        date.replace(day=1)
        + relativedelta.relativedelta(months=1)
        - relativedelta.relativedelta(days=1)
    )


def last_day_of_year(date):
    return datetime.date(date.year, 12, 31)


def get_dates_in(
    start_date: datetime.date, end_date: datetime.date
) -> Generator[datetime.date, None, None]:
    ret_val = []
    if start_date <= end_date:
        delta = end_date - start_date
        for i in range(delta.days + 1):
            candidate = start_date + datetime.timedelta(days=i)
            ret_val.append(candidate)
    else:
        delta = start_date - end_date
        for i in range(delta.days + 1):
            candidate = start_date - datetime.timedelta(days=i)
            ret_val.append(candidate)

    return ret_val


def get_month_start(p_date: datetime.date):
    return datetime.date(p_date.year, p_date.month, 1)


def get_quarter(p_date: datetime.date) -> int:
    return (p_date.month - 1) // 3 + 1


def get_first_day_of_the_quarter(p_date: datetime.date) -> datetime.date:
    return datetime.date(p_date.year, 3 * ((p_date.month - 1) // 3) + 1, 1)


def get_last_day_of_the_quarter(p_date: datetime.date):
    quarter = get_quarter(p_date)
    return datetime.date(
        p_date.year + 3 * quarter // 12, 3 * quarter % 12 + 1, 1
    ) + relativedelta.relativedelta(days=-1)


def get_quarters(min_date: datetime.date, max_date: datetime.date):
    curr_date = get_quarter_first_day(min_date)
    while curr_date < max_date:
        yield curr_date
        curr_date = curr_date + relativedelta.relativedelta(months=3)


def get_months(min_date: datetime.date, max_date: datetime.date):
    curr_date = get_month_start(min_date)
    while curr_date <= max_date:
        yield curr_date
        curr_date = curr_date + relativedelta.relativedelta(months=1)


def get_years(min_date: datetime.date, max_date: datetime.date):
    curr_date = get_year_start_date(min_date)
    while curr_date <= max_date:
        yield curr_date
        curr_date = curr_date + relativedelta.relativedelta(years=1)


def get_week_start_date(date: datetime.date) -> datetime.date:
    return date - datetime.timedelta(days=date.weekday())


def get_year_start_date(date: datetime.date) -> datetime.date:
    return datetime.date(date.year, 1, 1)


def exclude_range(
    date_from: datetime.date,
    date_to: datetime.date,
    value,
    exclude_from: datetime.date,
    exclude_to: datetime.date,
) -> List[Tuple[datetime.date, datetime.date]]:
    lst = sorted([date_from, date_to, exclude_from, exclude_to])
    index_first = lst.index(exclude_from)
    index_last = lst.index(exclude_to)
    include1: List[Tuple[int]] = []
    if index_first > 0:
        include1 += [(0, index_first, -1)]
    if index_last < 3:
        include1 += [(index_last, 3, 1)]
    f = [
        (
            lst[x[0]] - datetime.timedelta(days=x[2]),
            lst[x[1]] + datetime.timedelta(days=x[2]),
            value,
        )
        for x in include1
    ]
    return f
