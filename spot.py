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
    image_url: Optional[str] = None  # ← 画像URLを追加
    source: str = ""
    # LLM またはルールベースが埋めるフィールド
    stay_time_minutes: Optional[int] = None
    reason: Optional[str] = None
    # スコア詳細（デバッグ・説明用）
    score_breakdown: Optional[Dict[str, float]] = None
    total_score: Optional[float] = None

    # 🔹 Hotpepper API の shop JSON → Spot に変換
    @classmethod
    def from_hotpepper_json(cls, shop: dict) -> "Spot":
        # 基本情報
        name = shop.get("name", "不明な店舗")
        address = shop.get("address", "")

        # 緯度・経度
        lat = 0.0
        lng = 0.0
        try:
            if shop.get("lat") is not None:
                lat = float(shop.get("lat"))
            if shop.get("lng") is not None:
                lng = float(shop.get("lng"))
        except (TypeError, ValueError):
            pass

        # ジャンル名
        genre = ""
        g = shop.get("genre")
        if isinstance(g, dict):
            genre = g.get("name", "") or ""

        # 画像URL
        image_url = None
        photo = shop.get("photo")
        if isinstance(photo, dict):
            pc = photo.get("pc")
            if isinstance(pc, dict):
                image_url = pc.get("l") or pc.get("m") or pc.get("s")

        # 説明用
        desc_parts = []

        catchcopy = shop.get("catch")
        if catchcopy:
            desc_parts.append(catchcopy)

        budget_str = None
        b = shop.get("budget")
        if isinstance(b, dict):
            budget_str = b.get("average")
        if budget_str:
            desc_parts.append(f"予算目安: {budget_str}")

        description = " / ".join(desc_parts) if desc_parts else None

        # スコア用の簡単な情報
        score_breakdown: Dict[str, float] = {
            "desc_len": float(len(description or "")),
        }
        if budget_str:
            # scoring_restaurant で参照する budget_text
            score_breakdown["budget_text"] = 0.0  # 型合わせ用のダミー

        spot = cls(
            spot_type="restaurant",
            name=name,
            address=address,
            lat=lat,
            lng=lng,
            genre=genre,
            rating=None,
            reviews_count=None,
            description=description,
            image_url=image_url,
            source="hotpepper",
        )
        spot.score_breakdown = score_breakdown
        return spot

    # 🔹（必要なら）Google Places の JSON → Spot に変換する用
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
            image_url=None,
            source="google_places",
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
