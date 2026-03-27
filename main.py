import os
import re
import cloudscraper
import time
from bs4 import BeautifulSoup
from datetime import datetime
from notion_client import Client

# 读取 GitHub Secrets
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
REPO = os.getenv("GITHUB_REPOSITORY")

CME_BASE = "https://www.cmegroup.com"
BULLETIN_URL = f"{CME_BASE}/market-data/daily-bulletin.html"

def run():
    # 创建 scraper 实例，模拟浏览器
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    os.makedirs("downloads", exist_ok=True)
    
    targets = {
        "future": {"pattern": "Section62", "notion_col": "File", "found": False, "data": {}},
        "option": {"pattern": "Section64", "notion_col": "Option File", "found": False, "data": {}}
    }

    print("Step 1: 使用 cloudscraper 绕过防护访问页面...")
    try:
        resp = scraper.get(BULLETIN_URL, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                for key, target in targets.items():
                    if not target["found"] and target["pattern"] in href:
                        target["url"] = CME_BASE + href if href.startswith('/') else href
                        target["found"] = True
        else:
            print(f"网页访问失败 (Status: {resp.status_code})")
    except Exception as e:
        print(f"访问异常: {e}")

    # Step 2: 下载逻辑（同样使用 scraper）
    fallback_urls = {
        "future": f"{CME_BASE}/daily_bulletin/current/Section62_Metals_Futures_Products.pdf",
        "option": f"{CME_BASE}/daily_bulletin/current/Section64_Metals_Option_Products.pdf"
    }

    for key, target in targets.items():
        download_url = target.get("url") or fallback_urls[key]
        filename = download_url.split('/')[-1]
        
        print(f"正在尝试下载 {key}: {filename}")
        try:
            # 增加随机延迟防止被封
            time.sleep(2)
            file_resp = scraper.get(download_url, timeout=30)
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

    # Step 3: 提取日期并更新 Notion
    if not any(t["found"] for t in targets.values()):
        print("❌ 依然无法绕过防火墙，请考虑备选建议。")
        return

    sample_file = ""
    for t in targets.values():
        if t["found"]:
            sample_file = t["data"]["filename"]
            break
    
    date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', sample_file)
    report_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else datetime.now().strftime("%Y-%m-%d")

    properties = {
        "Name": {"title": [{"text": {"content": f"Metals OI_{report_date}"}}]},
        "Date": {"date": {"start": report_date}}
    }

    for key, target in targets.items():
        if target["found"]:
            properties[target["notion_col"]] = {
                "files": [{"name": target["data"]["filename"], "type": "external", "external": {"url": target["data"]["url"]}}]
            }

    print("Step 4: 写入 Notion...")
    notion = Client(auth=NOTION_TOKEN)
    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=properties)
        print(f"🎉 同步完成！日期: {report_date}")
    except Exception as e:
        print(f"Notion 写入失败: {e}")

if __name__ == "__main__":
    run()
