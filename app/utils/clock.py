"""Single source of 'now' so the timestamp policy lives in one place."""

from datetime import date, datetime

import config


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def today() -> date:
    return date.today()


def ts(value: datetime | None = None) -> str:
    return (value or now()).strftime(config.TIMESTAMP_FORMAT)


def ds(value: date | None = None) -> str:
    return (value or today()).strftime(config.DATE_FORMAT)


def parse_date(text: str) -> date:
    return datetime.strptime(text[:10], config.DATE_FORMAT).date()


def parse_ts(text: str) -> datetime:
    return datetime.strptime(text, config.TIMESTAMP_FORMAT)
