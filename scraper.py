#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import hashlib

import cloudscraper
from bs4 import BeautifulSoup
import cv2

# ==== 配置 ====
BRIGHTNESS_THRESHOLD = 130
BATCH_SIZE = 100
IMAGES_DIR = "ri"
GALLERIES_FILE = "galleries.json"
PROGRESS_FILE = "progress.json"
COUNT_FILE = os.path.join(IMAGES_DIR, "count.json")

FOLDERS = ["vd", "vl", "hd", "hl"]

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)


def load_json(filepath: str, default=None):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(filepath: str, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_file_hash(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_hash_registry() -> dict:
    registry_path = os.path.join(IMAGES_DIR, "hash_registry.json")
    return load_json(registry_path, {})


def save_hash_registry(registry: dict):
    registry_path = os.path.join(IMAGES_DIR, "hash_registry.json")
    save_json(registry_path, registry)


def get_folder_count(folder: str) -> int:
    folder_path = os.path.join(IMAGES_DIR, folder)
    if not os.path.exists(folder_path):
        return 0
    count = 0
    for f in os.listdir(folder_path):
        if f.endswith('.webp'):
            count += 1
    return count


def get_next_gallery():
    galleries = load_json(GALLERIES_FILE, [])
    progress = load_json(PROGRESS_FILE, {"completed": []})
    completed = set(progress.get("completed", []))
    
    for gallery in galleries:
        if gallery["url"] not in completed:
            return gallery
    return None


def mark_completed(url: str):
    progress = load_json(PROGRESS_FILE, {"completed": []})
    if url not in progress["completed"]:
        progress["completed"].append(url)
    save_json(PROGRESS_FILE, progress)


def scrape_images(url: str) -> list[dict]:
    print(f"🌐 正在爬取: {url}")
    
    try:
        resp = scraper.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        print(f"✅ 页面请求成功")
    except Exception as e:
        print(f"❌ 请求页面失败: {e}")
        return []
    
    soup = BeautifulSoup(resp.text, "lxml")
    images = []
    links = soup.find_all("a", {"data-fancybox": True})
    
    for idx, link in enumerate(links, 1):
        href = link.get("href", "")
        if href and href.startswith("http"):
            images.append({"url": href, "index": idx})
    
    print(f"✅ 找到 {len(images)} 张图片")
    return images


def download_image(url: str, save_path: str) -> bool:
    try:
        resp = scraper.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return False


def convert_to_webp(input_path: str, output_path: str) -> bool:
    try:
        img = cv2.imread(input_path)
        if img is None:
            return False
        cv2.imwrite(output_path, img, [cv2.IMWRITE_WEBP_QUALITY, 85])
        return True
    except:
        return False


def get_image_info(path: str, threshold=BRIGHTNESS_THRESHOLD) -> dict | None:
    try:
        img = cv2.imread(path)
        if img is None:
            return None
        
        height, width = img.shape[:2]
        if width < 10 or height < 10:
            return None
        
        orientation = "h" if width >= height else "v"
        
        img_resized = cv2.resize(img, (100, 100))
        lab = cv2.cvtColor(img_resized, cv2.COLOR_BGR2LAB)
        avg_l = lab[:, :, 0].mean()
        brightness = "d" if avg_l < threshold else "l"
        
        folder = orientation + brightness
        
        print(f"🖼️ {width}x{height} → L={avg_l:.1f} → {folder}")
        
        return {"folder": folder}
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return None


def update_count_file():
    count = {}
    for folder in FOLDERS:
        count[folder] = get_folder_count(folder)
    save_json(COUNT_FILE, count)
    print(f"📊 更新 count.json: {count}")


def process_gallery(gallery: dict) -> str:
    """
    返回状态:
    - "success": 成功处理
    - "empty": 没有图片，需跳过
    - "error": 出错
    """
    url = gallery["url"]
    folder_name = gallery["folder"]
    
    print(f"\n{'='*50}")
    print(f"📂 处理: {folder_name}")
    print(f"{'='*50}\n")
    
    temp_dir = "temp_download"
    os.makedirs(temp_dir, exist_ok=True)
    for folder in FOLDERS:
        os.makedirs(os.path.join(IMAGES_DIR, folder), exist_ok=True)
    
    images = scrape_images(url)
    
    # ⭐ 关键修改：没有图片时返回 "empty"
    if not images:
        print(f"⚠️ 没有图片，跳过此gallery")
        return "empty"
    
    hash_registry = load_hash_registry()
    folder_counts = {folder: get_folder_count(folder) for folder in FOLDERS}
    
    new_count = 0
    for img_info in images[:BATCH_SIZE]:
        idx = img_info["index"]
        temp_path = os.path.join(temp_dir, f"temp_{idx}")
        
        print(f"\n📥 下载 {idx}/{len(images)}...")
        
        if not download_image(img_info["url"], temp_path):
            continue
        
        file_hash = get_file_hash(temp_path)
        
        if file_hash in hash_registry:
            print(f"⏭️ 跳过重复: {file_hash[:16]}...")
            os.remove(temp_path)
            continue
        
        info = get_image_info(temp_path)
        if info is None:
            os.remove(temp_path)
            continue
        
        target_folder = info["folder"]
        folder_counts[target_folder] += 1
        new_num = folder_counts[target_folder]
        
        final_path = os.path.join(IMAGES_DIR, target_folder, f"{new_num}.webp")
        
        if convert_to_webp(temp_path, final_path):
            hash_registry[file_hash] = f"{target_folder}/{new_num}.webp"
            new_count += 1
            print(f"✅ 保存: {target_folder}/{new_num}.webp")
        
        os.remove(temp_path)
    
    save_hash_registry(hash_registry)
    update_count_file()
    
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    
    print(f"\n✅ 完成: {folder_name}")
    print(f"📊 新增 {new_count} 张")
    
    return "success"


def main():
    print("🚀 开始运行")
    
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    # ⭐ 关键修改：循环处理，跳过空gallery
    while True:
        gallery = get_next_gallery()
        if gallery is None:
            print("\n🎉 所有图仓已处理完成!")
            break
        
        result = process_gallery(gallery)
        
        if result == "empty":
            # 空gallery，标记完成并继续下一个
            print(f"⏭️ 跳过，继续下一个...\n")
            mark_completed(gallery["url"])
            continue
        elif result == "success":
            # 成功处理，标记完成并退出
            mark_completed(gallery["url"])
            break
        else:
            # 出错，不标记，退出等待重试
            print(f"❌ 处理出错，下次重试")
            break
    
    print("\n🏁 结束")


if __name__ == "__main__":
    main()
