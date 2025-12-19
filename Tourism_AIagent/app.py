# app.py
import os
from typing import List
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, Response

from hotpepper_client import HotpepperClient
from google_client import GooglePlacesClient
from scoring_restaurant import calc_restaurant_scores
from scoring_place import calc_place_scores
from reasoner import generate_reason_and_stay_time
from spot import Spot

from urllib.parse import urlparse
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = "change-this-secret"  # フラッシュメッセージ用（適当に変更OK）

HOTPEPPER_API_KEY = os.getenv("HOTPEPPER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

hotpepper_client = HotpepperClient(HOTPEPPER_API_KEY) if HOTPEPPER_API_KEY else None
google_client = GooglePlacesClient(GOOGLE_API_KEY) if GOOGLE_API_KEY else None


# ---- UI用の選択肢 ----

RESTAURANT_GENRES = {
    "ramen": "ラーメン",
    "washoku": "和食",
    "western": "洋食・欧風料理",
    "chinese": "中華料理",
    "asian": "アジア・エスニック（韓国・タイ・インド等）",
    "cafe_sweets": "カフェ・スイーツ",
    "yakiniku": "焼肉",
    "okonomiyaki": "お好み焼き・鉄板焼き",
    "fastfood": "ファーストフード",
    "family_restaurant": "ファミレス",
}
PLACE_GENRES = {
    "nature": "自然・公園",
    "sightseeing": "観光名所",
    "history_culture": "歴史・寺社・文化",
    "shopping": "ショッピングエリア",
    "museum": "美術館・博物館",
    "themepark": "テーマパーク・遊園地",
    "zoo_aquarium": "動物園・水族館",
    "hot_spring": "温泉・スパ",
}

RESTAURANT_PRIORITIES = {
    "budget": "予算重視",
    "quality": "クオリティ重視",
    "distance": "距離重視（将来拡張）",
    "balance": "バランス",
}

PLACE_PRIORITIES = {
    "popularity": "人気（評価・口コミ）重視",
    "genre": "ジャンル一致重視",
    "distance": "距離重視",
    "balance": "バランス",
}


def map_genre_key_to_label(category: str, key: str) -> str:
    if category == "restaurant":
        return RESTAURANT_GENRES.get(key, key)
    else:
        return PLACE_GENRES.get(key, key)


def map_place_type_from_genre_key(genre_key: str) -> str:
    if genre_key == "nature":
        return "park"
    if genre_key == "sightseeing":
        return "tourist_attraction"
    if genre_key == "history_culture":
        return "tourist_attraction"
    if genre_key == "shopping":
        return "shopping_mall"
    if genre_key == "museum":
        return "museum"
    if genre_key == "themepark":
        return "amusement_park"
    if genre_key == "zoo_aquarium":
        return "zoo"
    if genre_key == "hot_spring":
        return "spa"
    return "tourist_attraction"


@app.route("/", methods=["GET"])
def index():
    if not HOTPEPPER_API_KEY or not GOOGLE_API_KEY:
        flash("HOTPEPPER_API_KEY と GOOGLE_API_KEY を .env に設定してください。", "error")

    return render_template(
        "index.html",
        restaurant_genres=RESTAURANT_GENRES,
        place_genres=PLACE_GENRES,
        restaurant_priorities=RESTAURANT_PRIORITIES,
        place_priorities=PLACE_PRIORITIES,
        google_api_key=GOOGLE_API_KEY,
    )


@app.route("/recommend", methods=["POST"])
def recommend():
    category = request.form.get("category")
    genre_key = request.form.get("genre")
    priority = request.form.get("priority")
    station = request.form.get("station", "").strip()
    search_mode = request.form.get("search_mode", "station")

    radius_str = request.form.get("radius", "1000")
    radius = int(radius_str)

    lat_str = request.form.get("lat")
    lng_str = request.form.get("lng")
    origin_lat = origin_lng = None
    if lat_str and lng_str:
        try:
            origin_lat = float(lat_str)
            origin_lng = float(lng_str)
        except ValueError:
            origin_lat = origin_lng = None

    # 入力チェック
    if not category or not genre_key or not priority:
        flash("カテゴリ・ジャンル・優先度を選択してください。", "error")
        return redirect(url_for("index"))

    if search_mode == "station" and not station:
        flash("検索方法が『駅名』のときは、駅名を入力してください。", "error")
        return redirect(url_for("index"))

    if search_mode == "map" and origin_lat is None:
        flash("検索方法が『地図』のときは、地図をクリックして場所を選んでください。", "error")
        return redirect(url_for("index"))

    genre_label = map_genre_key_to_label(category, genre_key)

    ranked_spots: List[Spot] = []

    try:
        if category == "restaurant":
            if not hotpepper_client:
                raise RuntimeError("Hotpepper API キーが設定されていません。")
            if not google_client:
                raise RuntimeError("Google API キーが設定されていません。")

            # Hotpepper で候補店を取得（名前 + 位置だけ使う）
            hp_spots = hotpepper_client.search_restaurants(
                station_keyword=station,
                user_genre_keyword=genre_label,
                count=10,
                lat=origin_lat if search_mode == "map" else None,
                lng=origin_lng if search_mode == "map" else None,
            )

            google_spots: List[Spot] = []

            for hp in hp_spots:
                # 一致率UP: 店名 + 住所で検索
                query = f"{hp.name} {hp.address}".strip()

                # ① Google place_id を検索
                place_id = google_client.find_place_id(query, hp.lat, hp.lng)
                if not place_id:
                    continue

                # ② Google 詳細情報を取得
                details = google_client.get_place_details(place_id)
                if not details:
                    continue

                # ③ Google Photo の URL を取得（1枚目を採用）
                photos = details.get("photos", [])
                image_url = None
                if photos:
                    photo_ref = photos[0].get("photo_reference")
                    if photo_ref:
                        image_url = google_client.get_photo_url(photo_ref)

                # ④ Spot オブジェクト化（Google情報のみを使う）
                spot_obj = Spot.from_google_details(details, image_url)
                google_spots.append(spot_obj)

            # スコア計算
            scored_spots = [calc_restaurant_scores(s, priority) for s in google_spots]

        else:
            if not google_client:
                raise RuntimeError("Google API キーが設定されていません。")

            # 観光：search_mode に応じて起点座標を決める
            if search_mode == "map" and origin_lat is not None and origin_lng is not None:
                station_lat, station_lng = origin_lat, origin_lng
            else:
                station_lat, station_lng = google_client.geocode_station(station)

            place_type = map_place_type_from_genre_key(genre_key)
            spots = google_client.nearby_places(station_lat, station_lng, place_type, radius=radius)

            scored_spots = [
                calc_place_scores(s, priority, station_lat, station_lng, place_type)
                for s in spots
            ]

        # total_score があるものだけ → スコア順に全部並べる
        scored_spots = [s for s in scored_spots if s.total_score is not None]
        scored_spots.sort(key=lambda s: s.total_score, reverse=True)
        ranked_spots = [generate_reason_and_stay_time(s) for s in scored_spots]

    except Exception as e:
        print("ERROR:", e)
        flash(f"推薦中にエラーが発生しました: {e}", "error")
        return redirect(url_for("index"))

    if not ranked_spots:
        flash("条件に合うスポットが見つかりませんでした。駅名やジャンルを変えて再度お試しください。", "error")
        return redirect(url_for("index"))

    return render_template(
        "result.html",
        category=category,
        genre_label=genre_label,
        priority=priority,
        station=station,
        spots=ranked_spots,   # カードスタック用のリスト
    )


# ---- 画像プロキシ（Google Photo API の403対策）----

ALLOWED_IMAGE_HOSTS = {
    "maps.googleapis.com",
    "lh3.googleusercontent.com",
}

@app.route("/photo")
def photo_proxy():
    """
    Google Places Photo 等の画像をサーバー側で取得して返す。
    ブラウザ直アクセスだと403になりやすいのを回避する。
    """
    img_url = request.args.get("url", "")
    if not img_url:
        return ("missing url", 400)

    # 簡易セキュリティ（オープンプロキシ防止）
    try:
        u = urlparse(img_url)
    except Exception:
        return ("bad url", 400)

    if u.scheme not in ("http", "https"):
        return ("bad scheme", 400)

    if u.hostname not in ALLOWED_IMAGE_HOSTS:
        return ("host not allowed", 403)

    try:
        r = requests.get(img_url, timeout=8, allow_redirects=True, stream=True)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "image/jpeg")
        data = r.content

        resp = Response(data, mimetype=content_type)
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    except Exception as e:
        print("PHOTO_PROXY_ERROR:", e)
        return ("failed to fetch image", 502)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
