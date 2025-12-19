# reasoner.py
from spot import Spot


def generate_reason_and_stay_time(spot: Spot) -> Spot:
    """
    本来は LLM に投げる関数。v1ではルールベースで簡易生成。
    """
    if spot.spot_type == "restaurant":
        stay = 60
    else:
        stay = 90

    parts = [f"{spot.name} は {spot.address} にあるスポットです。"]

    if spot.spot_type == "restaurant":
        bd = spot.score_breakdown or {}
        b = bd.get("budget_score")
        q = bd.get("quality_score")
        parts.append("飲食店として")

        if b is not None:
            if b >= 5:
                parts.append("とても安い価格帯で利用でき、")
            elif b >= 4:
                parts.append("比較的利用しやすい価格帯で、")
            elif b >= 3:
                parts.append("標準的な価格帯で、")
            else:
                parts.append("少し高めの価格帯ですが、")

        if q is not None:
            if q >= 5:
                parts.append("設備や紹介文の情報量が多く、品質面でも期待できるお店です。")
            else:
                parts.append("基本的な設備情報が揃っているお店です。")

    else:
        bd = spot.score_breakdown or {}
        p = bd.get("popularity_score")
        d_km = bd.get("distance_km")

        if p is not None:
            if p >= 7:
                parts.append("Google 上での評価や口コミ数が特に高く、人気の観光スポットです。")
            elif p >= 5:
                parts.append("評価と口コミ数がバランス良く高いスポットです。")
            else:
                parts.append("一定の評価を得ているスポットです。")

        if d_km is not None:
            if d_km <= 1:
                parts.append("駅から徒歩圏内にあり、アクセスしやすい点もおすすめです。")
            elif d_km <= 5:
                parts.append("駅から電車やバスで移動しやすい距離にあります。")
            else:
                parts.append("少し距離はありますが、目的地として訪れる価値があります。")

    spot.stay_time_minutes = stay
    spot.reason = "".join(parts)
    return spot
