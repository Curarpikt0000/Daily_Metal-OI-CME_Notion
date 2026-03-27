import os
import re
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from notion_client import Client

# 读取 GitHub Secrets
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
REPO = os.getenv("GITHUB_REPOSITORY")

# 目标基础 URL
CME_BASE = "https://www.cmegroup.com"
BULLETIN_URL = f"{CME_BASE}/market-data/daily-bulletin.html"

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
        'Connection': 'keep-alive'
    }

def run():
    session = requests.Session()
    headers = get_headers()
    os.makedirs("downloads", exist_ok=True)
    
    # 定义目标
    targets = {
        "future": {"pattern": "Section62", "notion_col": "File", "found": False, "data": {}},
        "option": {"pattern": "Section64", "notion_col": "Option File", "found": False, "data": {}}
    }

    print("Step 1: 尝试模拟浏览器访问 CME 官网获取 Cookie...")
    try:
        session.get(CME_BASE, headers=headers, timeout=20)
        time.sleep(2) # 稍微歇一会，模拟人类阅读
        
        print("Step 2: 访问 Daily Bulletin 页面...")
        resp = session.get(BULLETIN_URL, headers=headers, timeout=20)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                for key, target in targets.items():
                    if not target["found"] and target["pattern"] in href:
                        target["url"] = CME_BASE + href if href.startswith('/') else href
                        target["found"] = True
        else:
            print(f"网页访问依然受阻 (Status: {resp.status_code})，启动强制直接探测逻辑...")
    except Exception as e:
        print(f"访问过程出错: {e}，尝试兜底方案...")

    # Step 3: 如果网页抓不到链接，尝试直接探测当日固定路径
    # CME 的路径规律通常是 /daily_bulletin/current/Section62_Metals_Futures_Products.pdf
    fallback_urls = {
        "future": f"{CME_BASE}/daily_bulletin/current/Section62_Metals_Futures_Products.pdf",
        "option": f"{CME_BASE}/daily_bulletin/current/Section64_Metals_Option_Products.pdf"
    }

    for key, target in targets.items():
        download_url = target.get("url") or fallback_urls[key]
        filename = download_url.split('/')[-1]
        
        print(f"正在尝试下载 {key}: {filename}")
        try:
            file_resp = session.get(download_url, headers=headers, timeout=20)
            if file_resp.status_code == 200:
                filepath = f"downloads/{filename}"
                with open(filepath, 'wb') as f:
                    f.write(file_resp.content)
                
                target["data"] = {
                    "filename": filename,
                    "url": f"https://raw.githubusercontent.com/{REPO}/main/{filepath}"
                }
                target["found"] = True
                print(f"成功获取 {key} 文件")
            else:
                print(f"下载 {key} 失败，状态码: {file_resp.status_code}")
        except Exception as e:
            print(f"下载 {key} 时发生异常: {e}")

    # Step 4: 提取日期并更新 Notion
    if not any(t["found"] for t in targets.values()):
        print("❌ 未能获取到任何文件，任务中止。")
        return

    # 日期提取逻辑
    sample_file = ""
    for t in targets.values():
        if t["found"]:
            sample_file = t["data"]["filename"]
            break
    
    date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', sample_file)
    report_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else datetime.now().strftime("%Y-%m-%d")

    # 构造 Notion 属性
    properties = {
        "Name": {"title": [{"text": {"content": f"Metals OI_{report_date}"}}]},
        "Date": {"date": {"start": report_date}}
    }

    for key, target in targets.items():
        if target["found"]:
            properties[target["notion_col"]] = {
                "files": [{"name": target["data"]["filename"], "type": "external", "external": {"url": target["data"]["url"]}}]
            }

    print("Step 5: 写入 Notion...")
    notion = Client(auth=NOTION_TOKEN)
    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=properties)
        print(f"🎉 任务圆满完成！日期: {report_date}")
    except Exception as e:
        print(f"Notion 写入失败: {e}")

if __name__ == "__main__":
    run()
