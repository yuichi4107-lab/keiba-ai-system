"""帯広ばんえい競馬のレース結果データスクレイパー

地方競馬の公式サイト (keiba.go.jp) からレース結果データを取得する。

URL構造:
  - レース一覧: /KeibaWeb/TodayRaceInfo/RaceList?k_raceDate=YYYY/MM/DD&k_babaCode=36
  - 出馬表:     /KeibaWeb/TodayRaceInfo/DebaTable?k_raceDate=YYYY/MM/DD&k_raceNo=N&k_babaCode=36
  - 成績:       /KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=YYYY/MM/DD&k_raceNo=N&k_babaCode=36
"""

import logging
import re
import time
from datetime import date, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config.settings import (
    OBIHIRO_COURSE_CODE,
    RAW_DATA_DIR,
    REQUEST_INTERVAL,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

BASE = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo"


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

    def _get_html(self, url: str, params: dict | None = None) -> str | None:
        """GETリクエストを送信してHTML文字列を返す（pandas.read_html用）"""
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            time.sleep(REQUEST_INTERVAL)
            return resp.text
        except requests.RequestException as e:
            logger.error("リクエスト失敗: %s - %s", url, e)
            return None

    def get_race_list(self, race_date: date) -> list[dict]:
        """指定日のレース一覧を取得する"""
        date_str = race_date.strftime("%Y/%m/%d")
        params = {"k_raceDate": date_str, "k_babaCode": OBIHIRO_COURSE_CODE}
        soup = self._get(f"{BASE}/RaceList", params=params)
        if soup is None:
            return []

        races = []
        # レース一覧ページからリンクを抽出
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "RaceMarkTable" in href or "DebaTable" in href:
                # レース番号をURLパラメータから抽出
                race_no_match = re.search(r"k_raceNo=(\d+)", href)
                if race_no_match:
                    race_no = race_no_match.group(1)
                    # 重複チェック
                    if not any(r["race_no"] == race_no for r in races):
                        races.append(
                            {
                                "date": date_str,
                                "race_no": race_no,
                            }
                        )

        logger.info("%s: %d レース取得", date_str, len(races))
        return races

    def get_race_result(self, race_date: date, race_no: str) -> list[dict]:
        """レース結果の詳細を取得する

        pandas.read_html でテーブルを取得し、
        BeautifulSoupで補足情報（レース名等）を取得する。
        """
        date_str = race_date.strftime("%Y/%m/%d")
        params = {
            "k_raceDate": date_str,
            "k_raceNo": race_no,
            "k_babaCode": OBIHIRO_COURSE_CODE,
        }

        # HTML取得
        html = self._get_html(f"{BASE}/RaceMarkTable", params=params)
        if html is None:
            return []

        soup = BeautifulSoup(html, "lxml")

        # レース情報を取得
        race_name = ""
        distance = None
        track_condition = ""

        # レース名
        for elem in soup.find_all(["h3", "span", "div"]):
            text = elem.get_text(strip=True)
            if text and "レース" in text and len(text) < 50:
                race_name = text
                break

        # 距離・馬場情報
        page_text = soup.get_text()
        dist_match = re.search(r"(\d{2,4})\s*m", page_text)
        if dist_match:
            distance = int(dist_match.group(1))

        for cond in ["良", "稍重", "重", "不良"]:
            if cond in page_text:
                track_condition = cond
                break

        # テーブルをpandasで読み込み
        try:
            tables = pd.read_html(html)
        except ValueError:
            logger.warning("テーブルが見つかりません: %s R%s", date_str, race_no)
            return []

        if not tables:
            return []

        # 最も列数が多いテーブルを結果テーブルとみなす
        result_table = max(tables, key=lambda t: len(t.columns))

        records = []
        for _, row in result_table.iterrows():
            record = self._parse_result_row(row, race_date, race_no, race_name, distance, track_condition)
            if record:
                records.append(record)

        return records

    def _parse_result_row(
        self,
        row: pd.Series,
        race_date: date,
        race_no: str,
        race_name: str,
        distance: int | None,
        track_condition: str,
    ) -> dict | None:
        """pandas DataFrameの行をパースしてレコードを作成"""
        values = [str(v) for v in row.values]
        text = " ".join(values)

        # 少なくとも馬名らしき日本語と数字が含まれること
        has_japanese = bool(re.search(r"[\u3040-\u9fff]{2,}", text))
        has_number = bool(re.search(r"\d", text))
        if not has_japanese or not has_number:
            return None

        record = {
            "race_date": race_date.strftime("%Y-%m-%d"),
            "race_no": race_no,
            "race_name": race_name,
            "distance": distance,
            "track_condition": track_condition,
        }

        # カラム数に応じてマッピング
        cols = list(row.index)
        vals = list(row.values)

        # 一般的な地方競馬結果テーブルのカラム順:
        # 着順, 枠番, 馬番, 馬名, 性齢, 馬体重, 騎手, タイム, 負担重量, 調教師, オッズ, 人気
        field_mappings = [
            ("finish_order", self._safe_int),
            ("post_position", self._safe_int),
            ("horse_number", self._safe_int),
            ("horse_name", str),
            ("sex_age", str),
            ("horse_weight", self._safe_float),
            ("jockey", str),
            ("time", str),
            ("weight_carry", self._safe_float),
            ("trainer", str),
            ("odds", self._safe_float),
            ("popularity", self._safe_int),
        ]

        for i, (field_name, converter) in enumerate(field_mappings):
            if i < len(vals):
                try:
                    val = str(vals[i]).strip()
                    if val in ("nan", "None", ""):
                        record[field_name] = None
                    else:
                        record[field_name] = converter(val)
                except (ValueError, TypeError):
                    record[field_name] = None

        # 性別と年齢を分離
        sex_age = record.get("sex_age", "")
        if sex_age and isinstance(sex_age, str) and len(sex_age) >= 2:
            record["sex"] = sex_age[0]
            record["age"] = self._safe_int(sex_age[1:])

        return record

    @staticmethod
    def _safe_int(value) -> int | None:
        try:
            return int(str(value).replace(",", "").strip())
        except (ValueError, AttributeError, TypeError):
            return None

    @staticmethod
    def _safe_float(value) -> float | None:
        try:
            return float(str(value).replace(",", "").strip())
        except (ValueError, AttributeError, TypeError):
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
                records = self.get_race_result(current, race["race_no"])
                all_records.extend(records)

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
