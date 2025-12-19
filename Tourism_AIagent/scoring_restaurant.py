# scoring_restaurant.py
from spot import Spot


def calc_restaurant_scores(spot: Spot, user_priority: str) -> Spot:
    """
    予算 / クオリティ / 距離(簡易)でスコアを算出。
    """
    breakdown = spot.score_breakdown or {}
    budget_text = str(breakdown.get("budget_text", ""))

    def budget_score(text: str) -> int:
        if "1000" in text:
            return 5
        elif "2000" in text:
            return 4
        elif "3000" in text:
            return 3
        elif "5000" in text:
            return 2
        elif text:
            return 1
        else:
            return 3  # 不明なら中間

    def quality_score(bd) -> int:
        score = 0
        if bd.get("private_room", 0) > 0:
            score += 2
        if bd.get("wifi", 0) > 0:
            score += 1
        if bd.get("parking", 0) > 0:
            score += 1
        desc_len = bd.get("desc_len", 0)
        if desc_len >= 50:
            score += 1
        if desc_len >= 120:
            score += 1
        return score

    # v1: 距離は固定値（将来は駅との距離で計算）
    def distance_score_fixed() -> int:
        return 3

    b_score = budget_score(budget_text)
    q_score = quality_score(breakdown)
    d_score = distance_score_fixed()

    weights_map = {
        "budget": (0.6, 0.2, 0.2),
        "quality": (0.2, 0.6, 0.2),
        "distance": (0.2, 0.2, 0.6),
        "balance": (1/3, 1/3, 1/3),
    }
    w_b, w_q, w_d = weights_map.get(user_priority, weights_map["balance"])

    total = b_score * w_b + q_score * w_q + d_score * w_d

    spot.score_breakdown = {
        "budget_score": b_score,
        "quality_score": q_score,
        "distance_score": d_score,
        "weight_budget": w_b,
        "weight_quality": w_q,
        "weight_distance": w_d,
    }
    spot.total_score = total
    return spot
