import requests
import os
import time
import json
from tqdm import tqdm

USER_ID    = "your_bhoonidhi_user_id"
PASSWORD   = "your_bhoonidhi_password"

BASE_URL   = "https://bhoonidhi.nrsc.gov.in"
AUTH_URL   = f"{BASE_URL}/bhoonidhi-api/auth/token"
SEARCH_URL = f"{BASE_URL}/bhoonidhi-api/stac/search"

OUTPUT_DIR = "./liss4_scenes"
os.makedirs(OUTPUT_DIR, exist_ok=True)

REGIONS = {
    "hyderabad": [78.2, 17.2, 78.7, 17.6],
    "pune":      [73.7, 18.4, 74.0, 18.7],
    "ahmedabad": [72.4, 22.9, 73.0, 23.3],
}

DATE_START = "2024-01-01"
DATE_END   = "2025-12-31"

CLOUDY_MIN = 60
CLEAR_MAX  = 10


def get_token():
    payload = {
        "userId": USER_ID,
        "password": PASSWORD,
        "grant_type": "password"
    }
    response = requests.post(AUTH_URL, json=payload)
    response.raise_for_status()
    data = response.json()
    token = data["access_token"]
    refresh = data["refresh_token"]
    expires_in = data.get("expires_in", 1200)
    print(f"Authenticated as {data['userId']}, token expires in {expires_in}s")
    return token, refresh


def refresh_token(refresh_tok):
    payload = {
        "userId": USER_ID,
        "refresh_token": refresh_tok,
        "grant_type": "refresh_token"
    }
    response = requests.post(AUTH_URL, json=payload)
    response.raise_for_status()
    data = response.json()
    print("Token refreshed.")
    return data["access_token"], data["refresh_token"]


def search_liss4_scenes(token, bbox, date_start, date_end,
                         cloud_min=0, cloud_max=100, max_results=50):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "collections": ["LISS-IV-MX"],
        "bbox": bbox,
        "datetime": f"{date_start}T00:00:00Z/{date_end}T23:59:59Z",
        "query": {
            "eo:cloud_cover": {
                "gte": cloud_min,
                "lte": cloud_max
            }
        },
        "limit": max_results,
        "sortby": [{"field": "datetime", "direction": "desc"}]
    }
    response = requests.post(SEARCH_URL, headers=headers, json=payload)
    response.raise_for_status()
    results = response.json()
    features = results.get("features", [])
    print(f"  Found {len(features)} scenes (cloud {cloud_min}-{cloud_max}%)")
    return features


def download_scene(token, scene, output_dir):
    scene_id = scene.get("id", "unknown")
    assets = scene.get("assets", {})

    band_keys = {
        "BAND2": ["BAND2", "band2", "B2", "green"],
        "BAND3": ["BAND3", "band3", "B3", "red"],
        "BAND4": ["BAND4", "band4", "B4", "nir"],
    }

    scene_dir = os.path.join(output_dir, scene_id)
    os.makedirs(scene_dir, exist_ok=True)

    with open(os.path.join(scene_dir, "BAND_META.txt"), "w") as f:
        props = scene.get("properties", {})
        f.write(f"scene_id: {scene_id}\n")
        f.write(f"datetime: {props.get('datetime', 'unknown')}\n")
        f.write(f"cloud_cover: {props.get('eo:cloud_cover', 'unknown')}\n")
        f.write(f"bbox: {scene.get('bbox', 'unknown')}\n")

    headers = {"Authorization": f"Bearer {token}"}
    downloaded = []

    for band_name, possible_keys in band_keys.items():
        asset = None
        for key in possible_keys:
            if key in assets:
                asset = assets[key]
                break

        if asset is None:
            print(f"  WARNING: {band_name} not found in assets for {scene_id}")
            print(f"  Available asset keys: {list(assets.keys())}")
            continue

        download_url = asset.get("href", "")
        if not download_url:
            print(f"  WARNING: no href for {band_name} in {scene_id}")
            continue

        out_path = os.path.join(scene_dir, f"{band_name}.tif")
        if os.path.exists(out_path):
            print(f"  Skipping {band_name} (already downloaded)")
            downloaded.append(band_name)
            continue

        print(f"  Downloading {band_name} from {download_url[:60]}...")
        r = requests.get(download_url, headers=headers, stream=True)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        with open(out_path, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=band_name
        ) as pbar:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))

        downloaded.append(band_name)
        time.sleep(0.5)

    return downloaded


if __name__ == "__main__":
    token, refresh_tok = get_token()
    token_start = time.time()

    for region_name, bbox in REGIONS.items():
        print(f"\n=== Region: {region_name} ===")

        if time.time() - token_start > 1080:
            token, refresh_tok = refresh_token(refresh_tok)
            token_start = time.time()

        cloudy_dir = os.path.join(OUTPUT_DIR, f"{region_name}_cloudy")
        clear_dir  = os.path.join(OUTPUT_DIR, f"{region_name}_clear")
        os.makedirs(cloudy_dir, exist_ok=True)
        os.makedirs(clear_dir, exist_ok=True)

        print(f"Searching CLOUDY scenes (cloud > {CLOUDY_MIN}%)...")
        cloudy_scenes = search_liss4_scenes(
            token, bbox, DATE_START, DATE_END,
            cloud_min=CLOUDY_MIN, cloud_max=100, max_results=10
        )

        print(f"Searching CLEAR scenes (cloud < {CLEAR_MAX}%)...")
        clear_scenes = search_liss4_scenes(
            token, bbox, DATE_START, DATE_END,
            cloud_min=0, cloud_max=CLEAR_MAX, max_results=5
        )

        print(f"\nDownloading {len(cloudy_scenes)} cloudy scenes...")
        for scene in cloudy_scenes:
            print(f"\n  Scene: {scene.get('id', 'unknown')}")
            download_scene(token, scene, cloudy_dir)

        print(f"\nDownloading {len(clear_scenes)} clear scenes...")
        for scene in clear_scenes:
            print(f"\n  Scene: {scene.get('id', 'unknown')}")
            download_scene(token, scene, clear_dir)

    print("\nDone.")
