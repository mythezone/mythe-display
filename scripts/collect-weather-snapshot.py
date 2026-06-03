#!/usr/bin/env python3
"""
Collect a Shenzhen weather snapshot for the kiosk clock widget.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "public/runtime/weather-shenzhen.json"
DEFAULT_REFRESH_MS = 1_800_000
DEFAULT_CITY = "深圳"
DEFAULT_LATITUDE = 22.5431
DEFAULT_LONGITUDE = 114.0579
DEFAULT_TIMEZONE = "Asia/Shanghai"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "晴",
    1: "少云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "霜雾",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷雨",
    96: "雷雨冰雹",
    99: "强雷雨冰雹",
}


def weather_label(code: int | None) -> str:
    if code is None:
        return "未知"
    return WEATHER_CODES.get(code, "未知")


def round_number(value: Any, digits: int = 1) -> float | None:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def int_number(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def build_url(latitude: float, longitude: float, timezone_name: str) -> str:
    query = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
            ]
        ),
        "forecast_days": 1,
        "timezone": timezone_name,
    }
    return f"{OPEN_METEO_URL}?{urllib.parse.urlencode(query)}"


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "mythe-display/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def collect(
    city: str,
    latitude: float,
    longitude: float,
    timezone_name: str,
    refresh_ms: int,
    timeout: float,
) -> dict[str, Any]:
    url = build_url(latitude, longitude, timezone_name)
    raw = fetch_json(url, timeout)
    current = raw.get("current") or {}
    daily = raw.get("daily") or {}

    current_code = int_number(current.get("weather_code"))
    daily_code = int_number((daily.get("weather_code") or [None])[0])

    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshMs": refresh_ms,
        "available": True,
        "source": "open-meteo",
        "sourceUrl": url,
        "location": {
            "name": city,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone_name,
        },
        "current": {
            "observedAt": current.get("time"),
            "temperatureC": round_number(current.get("temperature_2m")),
            "apparentTemperatureC": round_number(current.get("apparent_temperature")),
            "humidityPercent": int_number(current.get("relative_humidity_2m")),
            "windSpeedKmh": round_number(current.get("wind_speed_10m")),
            "weatherCode": current_code,
            "condition": weather_label(current_code),
        },
        "daily": {
            "date": (daily.get("time") or [None])[0],
            "temperatureMaxC": round_number((daily.get("temperature_2m_max") or [None])[0]),
            "temperatureMinC": round_number((daily.get("temperature_2m_min") or [None])[0]),
            "precipitationProbabilityPercent": int_number((daily.get("precipitation_probability_max") or [None])[0]),
            "weatherCode": daily_code,
            "condition": weather_label(daily_code),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Mythe Display 深圳天气 JSON 快照。")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help=f"输出路径，默认 {DEFAULT_OUTPUT}。")
    parser.add_argument("--city", default=DEFAULT_CITY, help="显示城市名称。")
    parser.add_argument("--latitude", type=float, default=DEFAULT_LATITUDE, help="纬度，默认深圳。")
    parser.add_argument("--longitude", type=float, default=DEFAULT_LONGITUDE, help="经度，默认深圳。")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE, help="天气 API 时区，默认 Asia/Shanghai。")
    parser.add_argument("--refresh-ms", type=int, default=DEFAULT_REFRESH_MS, help="刷新周期元数据，默认 30 分钟。")
    parser.add_argument("--timeout", type=float, default=8.0, help="API 请求超时秒数。")
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出。")
    args = parser.parse_args()

    try:
        payload = collect(args.city, args.latitude, args.longitude, args.timezone, args.refresh_ms, args.timeout)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as exc:
        print(f"采集天气失败: {exc}", file=sys.stderr)
        return 1

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    print(
        f"已写入 {output}: {payload['location']['name']} "
        f"{payload['current']['condition']} {payload['current']['temperatureC']}C"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
