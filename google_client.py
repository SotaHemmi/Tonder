# google_client.py
from typing import List, Tuple
import requests
from spot import Spot


class GooglePlacesClient:
    PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    PHOTO_URL = "https://maps.googleapis.com/maps/api/place/photo"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def geocode_station(self, station_name: str) -> Tuple[float, float]:
        """
        駅名から座標を取得（Geocoding API）。
        """
        params = {
            "address": station_name,
            "region": "jp",
            "key": self.api_key,
        }
        resp = requests.get(self.GEOCODE_URL, params=params, proxies={"http": None, "https": None}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            raise ValueError(f"駅名 '{station_name}' から座標を取得できませんでした。")

        loc = results[0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])

    def _build_photo_url(self, photo_ref: str, maxwidth: int = 800) -> str:
        return (
            f"{self.PHOTO_URL}?maxwidth={maxwidth}"
            f"&photo_reference={photo_ref}"
            f"&key={self.api_key}"
        )

    def nearby_places(self, center_lat: float, center_lng: float, place_type: str,
                      radius: int = 3000) -> List[Spot]:
        """
        指定座標から place_type ごとに Nearby Search。
        （/recommend 用の Spot リスト）
        """
        params = {
            "key": self.api_key,
            "location": f"{center_lat},{center_lng}",
            "radius": radius,
            "type": place_type,
            "language": "ja",
        }
        resp = requests.get(self.PLACES_NEARBY_URL, params=params, proxies={"http": None, "https": None}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        spots: List[Spot] = []

        for r in results:
            name = r.get("name", "")
            vicinity = r.get("vicinity", "")
            loc = r.get("geometry", {}).get("location", {})
            lat = float(loc.get("lat", 0))
            lng = float(loc.get("lng", 0))
            rating = r.get("rating")
            user_ratings_total = r.get("user_ratings_total")
            types = r.get("types", [])
            description = r.get("name", "")

            # 写真URL
            image_url = None
            photos = r.get("photos")
            if photos:
                ref = photos[0].get("photo_reference")
                if ref:
                    image_url = self._build_photo_url(ref, maxwidth=800)

            spot = Spot(
                spot_type="place",
                name=name,
                address=vicinity,
                lat=lat,
                lng=lng,
                genre=place_type,
                rating=float(rating) if rating is not None else None,
                reviews_count=int(user_ratings_total) if user_ratings_total is not None else None,
                description=description,
                image_url=image_url,
                source="google",
            )
            spot.score_breakdown = {
                "types": ",".join(types),
            }
            spots.append(spot)

        return spots
