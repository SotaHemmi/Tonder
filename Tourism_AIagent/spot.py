# spot.py
from dataclasses import dataclass
from typing import Optional, Dict
import math


@dataclass
class Spot:
    spot_type: str  # "restaurant" or "place"
    name: str
    address: str
    lat: float
    lng: float
    genre: str
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None  # 画像URL（Google / Hotpepper 両対応）
    source: str = ""
    # LLM またはルールベースが埋めるフィールド
    stay_time_minutes: Optional[int] = None
    reason: Optional[str] = None
    # スコア詳細（デバッグ・説明用）
    score_breakdown: Optional[Dict[str, float]] = None
    total_score: Optional[float] = None

    # 🔹 Hotpepper API の shop JSON → Spot に変換（検索用の最小構成）
    @classmethod
    def from_hotpepper_json(cls, shop: dict) -> "Spot":
        name = shop.get("name", "不明な店舗")
        address = shop.get("address", "")

        # 緯度・経度（文字列で返ることが多いので安全に変換）
        lat = 0.0
        lng = 0.0
        try:
            if shop.get("lat") is not None:
                lat = float(shop.get("lat"))
            if shop.get("lng") is not None:
                lng = float(shop.get("lng"))
        except (TypeError, ValueError):
            # 変換できなければ 0.0 のまま（あとで Google 側で弾かれる想定）
            pass

        # 🔸 Hotpepper のジャンル・説明・画像などはもう UI に使わないので捨てる
        return cls(
            spot_type="restaurant",
            name=name,
            address=address,
            lat=lat,
            lng=lng,
            genre="",          # ジャンルは Google の types 側で持つ
            rating=None,
            reviews_count=None,
            description=None,
            image_url=None,
            source="hotpepper",
        )

    # 🔹 Nearby Search の生 JSON → Spot にする汎用メソッド（観光用）
    @classmethod
    def from_google_place_json(cls, place: dict, genre_label: str = "") -> "Spot":
        name = place.get("name", "不明なスポット")
        address = place.get("vicinity") or place.get("formatted_address") or ""

        loc = place.get("geometry", {}).get("location", {})
        lat = 0.0
        lng = 0.0
        try:
            if loc.get("lat") is not None:
                lat = float(loc.get("lat"))
            if loc.get("lng") is not None:
                lng = float(loc.get("lng"))
        except (TypeError, ValueError):
            pass

        rating = place.get("rating")
        reviews_count = place.get("user_ratings_total")

        genre = genre_label
        if not genre:
            types = place.get("types") or []
            if types:
                genre = types[0]

        return cls(
            spot_type="place",
            name=name,
            address=address,
            lat=lat,
            lng=lng,
            genre=genre,
            rating=rating,
            reviews_count=reviews_count,
            description=None,
            image_url=None,           # 観光の画像は別で埋めるならここに
            source="google_places",
        )

    # 🔹 Google Place Details ＋ 画像URL → Spot に変換（グルメ用 / Google表示モード）
    @classmethod
    def from_google_details(cls, details: dict, image_url: Optional[str]) -> "Spot":
        name = details.get("name", "")
        address = details.get("formatted_address", "")

        loc = details.get("geometry", {}).get("location", {})
        lat = loc.get("lat", 0.0)
        lng = loc.get("lng", 0.0)

        rating = details.get("rating")
        reviews = details.get("user_ratings_total")
        types = details.get("types", [])

        return cls(
            spot_type="restaurant",
            name=name,
            address=address,
            lat=lat,
            lng=lng,
            genre=types[0] if types else "",
            rating=rating,
            reviews_count=reviews,
            description="",       # 説明文は今は空でもOK
            image_url=image_url,  # ← ここに Google の Photo URL が入る
            source="google_places",
            score_breakdown={"google_types": ",".join(types)} if types else None,
        )


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点の緯度経度から距離(km)を計算"""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
