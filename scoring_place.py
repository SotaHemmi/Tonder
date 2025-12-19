# scoring_place.py
from typing import List
from spot import Spot, haversine_km


def calc_place_scores(spot: Spot, user_priority: str,
                      station_lat: float, station_lng: float,
                      user_genre_keyword: str) -> Spot:
    """
    rating + reviews_count → popularity_score
    types とユーザー指定ジャンル → genre_score
    駅からの距離 → distance_score
    """
    rating = spot.rating
    reviews = spot.reviews_count or 0

    def popularity_score(rating_val, reviews_val: int) -> int:
        if rating_val is None:
            base = 2
        else:
            if rating_val >= 4.5:
                base = 5
            elif rating_val >= 4.0:
                base = 4
            elif rating_val >= 3.5:
                base = 3
            else:
                base = 1

        if reviews_val >= 1000:
            bonus = 3
        elif reviews_val >= 300:
            bonus = 2
        elif reviews_val >= 100:
            bonus = 1
        else:
            bonus = 0
        return base + bonus

    types_text = (spot.score_breakdown or {}).get("types", "")
    types_list: List[str] = types_text.split(",") if types_text else []

    def genre_score(types: List[str], genre_keyword: str) -> int:
        keyword = genre_keyword.lower()
        joined = " ".join(types).lower()
        if keyword and keyword in joined:
            return 3
        return 1

    dist_km = haversine_km(station_lat, station_lng, spot.lat, spot.lng)

    def distance_score_km(distance_km: float) -> int:
        if distance_km <= 1.0:
            return 5
        elif distance_km <= 3.0:
            return 4
        elif distance_km <= 5.0:
            return 3
        elif distance_km <= 10.0:
            return 2
        else:
            return 1

    p_score = popularity_score(rating, reviews)
    g_score = genre_score(types_list, user_genre_keyword)
    d_score = distance_score_km(dist_km)

    weights_map = {
        "popularity": (0.6, 0.2, 0.2),
        "genre": (0.2, 0.6, 0.2),
        "distance": (0.2, 0.2, 0.6),
        "balance": (1/3, 1/3, 1/3),
    }
    w_p, w_g, w_d = weights_map.get(user_priority, weights_map["balance"])

    total = p_score * w_p + g_score * w_g + d_score * w_d

    spot.score_breakdown = {
        "popularity_score": p_score,
        "genre_score": g_score,
        "distance_score": d_score,
        "distance_km": round(dist_km, 2),
        "weight_popularity": w_p,
        "weight_genre": w_g,
        "weight_distance": w_d,
    }
    spot.total_score = total
    return spot
