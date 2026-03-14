"""帯広ばんえい競馬のレース結果データスクレイパー

地方競馬の公式サイト (keiba.go.jp) からレース結果データを取得する。
"""

import logging
import time
from datetime import date, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config.settings import (
    BASE_URL,
    OBIHIRO_COURSE_CODE,
    RACE_RESULT_URL,
    RAW_DATA_DIR,
    REQUEST_INTERVAL,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


class BaneiScraper:
    """帯広ばんえい競馬データスクレイパー"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _get(self, url: str, params: dict | None = None) -> BeautifulSoup | None:
        """GETリクエストを送信してBeautifulSoupオブジェクトを返す"""
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            time.sleep(REQUEST_INTERVAL)
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            logger.error("リクエスト失敗: %s - %s", url, e)
            return None

    def get_race_list(self, race_date: date) -> list[dict]:
        """指定日のレース一覧を取得する"""
        date_str = race_date.strftime("%Y/%m/%d")
        params = {"k_raceDate": date_str, "k_baession": OBIHIRO_COURSE_CODE}
        soup = self._get(BASE_URL, params=params)
        if soup is None:
            return []

        races = []
        race_table = soup.find("table", class_="tblRaceList")
        if race_table is None:
            logger.info("レース情報なし: %s", date_str)
            return []

        for row in race_table.find_all("tr"):
            link = row.find("a")
            if link and "RaceMarkTable" in link.get("href", ""):
                race_no_cell = row.find("td")
                if race_no_cell:
                    race_info = {
                        "date": date_str,
                        "race_no": race_no_cell.get_text(strip=True),
                        "url": "https://www.keiba.go.jp" + link["href"],
                    }
                    races.append(race_info)

        logger.info("%s: %d レース取得", date_str, len(races))
        return races

    def get_race_result(self, race_url: str) -> dict | None:
        """レース結果の詳細を取得する"""
        soup = self._get(race_url)
        if soup is None:
            return None

        result = {"horses": []}

        # レース名・条件
        race_name_elem = soup.find("span", class_="raceName")
        if race_name_elem:
            result["race_name"] = race_name_elem.get_text(strip=True)

        race_info_elem = soup.find("div", class_="raceInfo")
        if race_info_elem:
            info_text = race_info_elem.get_text(strip=True)
            result["race_info"] = info_text
            # 距離を抽出
            if "m" in info_text:
                for part in info_text.split():
                    if "m" in part:
                        try:
                            result["distance"] = int(
                                part.replace("m", "").replace(",", "")
                            )
                        except ValueError:
                            pass
                        break

        # 馬柱テーブルから出走馬情報を取得
        result_table = soup.find("table", class_="tblResultData")
        if result_table is None:
            result_table = soup.find("table", id="resultLs")
        if result_table is None:
            # フォールバック: 最も大きなテーブルを使用
            tables = soup.find_all("table")
            if tables:
                result_table = max(tables, key=lambda t: len(t.find_all("tr")))

        if result_table is None:
            logger.warning("結果テーブルが見つかりません: %s", race_url)
            return result

        rows = result_table.find_all("tr")
        for row in rows[1:]:  # ヘッダー行をスキップ
            cells = row.find_all("td")
            if len(cells) < 6:
                continue

            horse = self._parse_horse_row(cells)
            if horse:
                result["horses"].append(horse)

        return result

    def _parse_horse_row(self, cells: list) -> dict | None:
        """テーブル行から馬データをパースする"""
        try:
            texts = [c.get_text(strip=True) for c in cells]

            horse = {
                "finish_order": self._safe_int(texts[0]),
                "post_position": self._safe_int(texts[1]),
                "horse_number": self._safe_int(texts[2]) if len(texts) > 2 else None,
                "horse_name": texts[3] if len(texts) > 3 else "",
                "sex_age": texts[4] if len(texts) > 4 else "",
                "horse_weight": self._safe_float(texts[5]) if len(texts) > 5 else None,
                "jockey": texts[6] if len(texts) > 6 else "",
                "time": texts[7] if len(texts) > 7 else "",
                "weight_carry": self._safe_float(texts[8]) if len(texts) > 8 else None,
                "trainer": texts[9] if len(texts) > 9 else "",
                "odds": self._safe_float(texts[10]) if len(texts) > 10 else None,
                "popularity": self._safe_int(texts[11]) if len(texts) > 11 else None,
            }

            # 性別と年齢を分離
            if horse["sex_age"] and len(horse["sex_age"]) >= 2:
                horse["sex"] = horse["sex_age"][0]
                horse["age"] = self._safe_int(horse["sex_age"][1:])

            return horse
        except (IndexError, ValueError) as e:
            logger.debug("馬データのパース失敗: %s", e)
            return None

    @staticmethod
    def _safe_int(value: str) -> int | None:
        try:
            return int(value.replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _safe_float(value: str) -> float | None:
        try:
            return float(value.replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    def scrape_date_range(
        self, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """指定期間のレース結果をスクレイピングしDataFrameで返す"""
        all_records = []
        current = start_date

        while current <= end_date:
            races = self.get_race_list(current)
            for race in races:
                result = self.get_race_result(race["url"])
                if result and result.get("horses"):
                    for horse in result["horses"]:
                        record = {
                            "race_date": current.strftime("%Y-%m-%d"),
                            "race_no": race["race_no"],
                            "race_name": result.get("race_name", ""),
                            "distance": result.get("distance"),
                            **horse,
                        }
                        all_records.append(record)

            current += timedelta(days=1)

        if not all_records:
            logger.warning("データが取得できませんでした")
            return pd.DataFrame()

        df = pd.DataFrame(all_records)
        return df

    def save_data(self, df: pd.DataFrame, filename: str = "race_results.csv"):
        """データをCSVに保存する"""
        filepath = RAW_DATA_DIR / filename
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info("保存完了: %s (%d 件)", filepath, len(df))
        return filepath
