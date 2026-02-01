"""Bot configuration dataclass."""

from dataclasses import dataclass
from datetime import time


@dataclass
class BotConfig:
	token: str
	daily_report_time: time = time(hour=21, minute=0, second=0)
	monthly_report_time: time = time(hour=9, minute=0, second=0)
	monthly_report_day: int = 1


__all__ = ["BotConfig"]
