import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.example.json"

@dataclass
class BotConfig:
    headless: bool = False
    browser_channel: str = "msedge"  # "msedge" or "chromium"
    run_daily_set: bool = True
    run_more_activities: bool = True
    run_desktop_search: bool = True
    desktop_searches: int = 35
    run_mobile_search: bool = True
    mobile_searches: int = 25
    min_delay_sec: float = 5.5
    max_delay_sec: float = 12.5
    fast_mode: bool = False
    run_msn_news: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    search_cooldown_batch_size: int = 4
    search_cooldown_wait_sec: float = 15.0
    account_labels: dict = None

    def __post_init__(self):
        if self.account_labels is None:
            self.account_labels = {}

    @classmethod
    def load(cls) -> "BotConfig":
        if not CONFIG_PATH.exists():
            default_conf = cls()
            if EXAMPLE_CONFIG_PATH.exists():
                try:
                    with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as f:
                        ex_data = json.load(f)
                    for k, v in ex_data.items():
                        if k in cls.__dataclass_fields__ and not str(getattr(default_conf, k, "")):
                            setattr(default_conf, k, v)
                except Exception:
                    pass
            default_conf.save()
            return default_conf

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            conf = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            conf = cls()

        # Fill missing fields from example config
        if EXAMPLE_CONFIG_PATH.exists():
            try:
                with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as f:
                    ex_data = json.load(f)
                for k, v in ex_data.items():
                    if k in cls.__dataclass_fields__ and not str(getattr(conf, k, "")):
                        setattr(conf, k, v)
            except Exception:
                pass

        return conf

    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)
