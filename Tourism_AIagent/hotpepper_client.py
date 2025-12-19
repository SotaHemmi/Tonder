# hotpepper_client.py
from typing import List, Dict
import requests
from spot import Spot


class HotpepperClient:
    BASE_URL = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_restaurants(
        self,
        station_keyword: str,
        user_genre_keyword: str,
        count: int = 20,
        lat: float | None = None,
        lng: float | None = None,
        range_code: int = 4,  # 1〜5 (1:300m, 2:500m, 3:1km, 4:2km, 5:3km)
    ) -> List[Spot]:

        params = {
            "key": self.api_key,
            "format": "json",
            "count": count,
        }

        if lat is not None and lng is not None:
            # 🔹 地図で選んだ位置を中心に検索
            params["lat"] = lat
            params["lng"] = lng
            params["range"] = range_code
            # 駅名は使わず、ジャンル（キーワード）だけを併用
            if user_genre_keyword:
                params["keyword"] = user_genre_keyword
        else:
            # 🔹 これまで通り「駅名＋ジャンル」のキーワード検索
            params["keyword"] = f"{station_keyword} {user_genre_keyword}"

        resp = requests.get(
            self.BASE_URL,
            params=params,
            proxies={"http": None, "https": None},  # プロキシ無効
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        shops = data.get("results", {}).get("shop", [])
        spots = [Spot.from_hotpepper_json(s) for s in shops]
        return spots
