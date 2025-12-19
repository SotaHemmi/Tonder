# app.py
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from hotpepper_client import HotpepperClient
from spot import Spot, haversine_km

load_dotenv()

app = Flask(__name__)
app.secret_key = "change-this-secret"  # フラッシュメッセージ用（適当に変更OK）

HOTPEPPER_API_KEY = os.getenv("HOTPEPPER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

hotpepper_client = HotpepperClient(HOTPEPPER_API_KEY) if HOTPEPPER_API_KEY else None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DEMO_VIDEO_DIR = BASE_DIR / "static" / "demo_videos"
TOURISM_DATA_PATH = DATA_DIR / "tourism_spots.json"

ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}


for directory in (DATA_DIR, UPLOAD_DIR, DEMO_VIDEO_DIR):
    directory.mkdir(parents=True, exist_ok=True)


DEFAULT_TOURISM_ITEMS = [
    {
        "id": "t-tokyo-tower",
        "type": "tourism",
        "name": "東京タワーナイトビュー",
        "lat": 35.65858,
        "lng": 139.74543,
        "description": "東京の象徴を真下から見上げるナイトツアー。ライトアップと街の光がシネマティックに映るデモ動画。",
        "videoPath": "/static/demo_videos/tokyo-night.mp4",
        "genre": "シティ",
    },
    {
        "id": "t-asakusa",
        "type": "tourism",
        "name": "浅草・雷門ドリフト",
        "lat": 35.71111,
        "lng": 139.79666,
        "description": "仲見世を通り抜けて夕暮れの雷門へ向かうショートトラベル。提灯と人流を強調したデモ動画。",
        "videoPath": "/static/demo_videos/asakusa-sunset.mp4",
        "genre": "カルチャー",
    },
    {
        "id": "t-minatomirai",
        "type": "tourism",
        "name": "横浜みなとみらい・夜景クルーズ",
        "lat": 35.45499,
        "lng": 139.63803,
        "description": "観覧車と海面の反射光をゆったり捉えたデモ動画。ループ再生で没入感を演出。",
        "videoPath": "/static/demo_videos/minatomirai-cruise.mp4",
        "genre": "ベイエリア",
    },
]


def init_tourism_data() -> None:
    if TOURISM_DATA_PATH.exists():
        return
    TOURISM_DATA_PATH.write_text(
        json.dumps(DEFAULT_TOURISM_ITEMS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_tourism_items() -> List[Dict[str, Any]]:
    init_tourism_data()
    try:
        data = json.loads(TOURISM_DATA_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_tourism_items(items: List[Dict[str, Any]]) -> None:
    TOURISM_DATA_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_tourism_video_path(spot_id: str, video_path: str) -> None:
    items = load_tourism_items()
    updated = False
    for item in items:
        if item.get("id") == spot_id:
            item["videoPath"] = video_path
            updated = True
            break
    if updated:
        save_tourism_items(items)


def radius_to_range_code(radius_m: int) -> int:
    """Hotpepper APIの range (1-5) に丸める"""
    if radius_m <= 300:
        return 1
    if radius_m <= 500:
        return 2
    if radius_m <= 1000:
        return 3
    if radius_m <= 2000:
        return 4
    return 5


def spot_to_gourmet_item(spot: Spot) -> Dict[str, Any]:
    """Spot → クライアント向けアイテムJSON"""
    spot_id = f"g-{int(spot.lat * 100000)}-{int(spot.lng * 100000)}"
    return {
        "id": spot_id,
        "type": "gourmet",
        "name": spot.name,
        "lat": spot.lat,
        "lng": spot.lng,
        "description": "",
        "videoPath": None,
        "imageUrl": spot.image_url,
        "star": None,  # Hotpepperに評価が無いため非表示
        "genre": spot.genre or "グルメ",
    }


@app.route("/", methods=["GET"])
def index():
    missing = []
    if not HOTPEPPER_API_KEY:
        missing.append("HOTPEPPER_API_KEY 未設定（グルメ検索が停止中）")
    if not GOOGLE_API_KEY:
        missing.append("GOOGLE_API_KEY 未設定（マップ表示が限定動作）")

    return render_template(
        "index.html",
        google_api_key=GOOGLE_API_KEY,
        hotpepper_ready=bool(hotpepper_client),
        missing_banner=" / ".join(missing) if missing else "",
    )


@app.route("/api/items", methods=["GET"])
def api_items():
    mode = request.args.get("mode", "tourism")
    lat_str = request.args.get("lat")
    lng_str = request.args.get("lng")
    radius_str = request.args.get("radius", "3000")

    try:
        lat = float(lat_str) if lat_str is not None else None
        lng = float(lng_str) if lng_str is not None else None
        radius = int(radius_str)
    except (TypeError, ValueError):
        return jsonify({"error": "lat, lng, radius は数値で指定してください。"}), 400

    if lat is None or lng is None:
        return jsonify({"error": "lat と lng は必須です。"}), 400

    if mode == "tourism":
        items = []
        for entry in load_tourism_items():
            try:
                d_km = haversine_km(
                    lat,
                    lng,
                    float(entry.get("lat", 0.0)),
                    float(entry.get("lng", 0.0)),
                )
            except (TypeError, ValueError):
                d_km = 0.0

            if radius > 0 and d_km * 1000 > radius:
                continue

            item = {
                "id": entry.get("id"),
                "type": "tourism",
                "name": entry.get("name"),
                "lat": entry.get("lat"),
                "lng": entry.get("lng"),
                "description": entry.get("description", ""),
                "videoPath": entry.get("videoPath"),
                "imageUrl": entry.get("imageUrl"),
                "star": None,
                "genre": entry.get("genre", "観光"),
                "distanceKm": round(d_km, 2),
            }
            items.append(item)

        items.sort(key=lambda x: x.get("distanceKm", 0))
        return jsonify({"items": items})

    if mode == "gourmet":
        if not hotpepper_client:
            return jsonify({"error": "Hotpepper APIキーを設定してください。"}), 400

        range_code = radius_to_range_code(radius)
        spots: List[Spot] = hotpepper_client.search_restaurants(
            station_keyword="",
            user_genre_keyword="",
            count=30,
            lat=lat,
            lng=lng,
            range_code=range_code,
        )
        items = [spot_to_gourmet_item(s) for s in spots]
        return jsonify({"items": items})

    return jsonify({"error": "mode は tourism / gourmet で指定してください。"}), 400


@app.route("/api/upload_video", methods=["POST"])
def api_upload_video():
    spot_id = request.form.get("spot_id")
    uploaded_file = request.files.get("file")

    if not spot_id or uploaded_file is None:
        return jsonify({"error": "spot_id とファイルが必須です。"}), 400

    ext = Path(uploaded_file.filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify(
            {
                "error": f"対応形式は {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))} です。",
            }
        ), 400

    filename = secure_filename(f"{spot_id}.{ext}")
    save_path = UPLOAD_DIR / filename
    uploaded_file.save(save_path)

    web_path = f"/static/uploads/{filename}"
    update_tourism_video_path(spot_id, web_path)

    return jsonify({"videoPath": web_path})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
