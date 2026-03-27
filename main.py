import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from notion_client import Client

# 读取 GitHub Secrets 里的环境变量
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
REPO = os.getenv("GITHUB_REPOSITORY") 

CME_URL = "https://www.cmegroup.com/market-data/daily-bulletin.html"

def run():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    print("正在访问 CME 网站获取最新链接...")
    try:
        response = requests.get(CME_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"访问失败: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    os.makedirs("downloads", exist_ok=True)

    # 定义抓取目标：62号是期货，64号是期权
    targets = {
        "future": {"pattern": "Section62", "notion_col": "File", "found": False, "data": {}},
        "option": {"pattern": "Section64", "notion_col": "Option File", "found": False, "data": {}}
    }

    # 1. 扫描网页链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        for key, target in targets.items():
            if not target["found"] and target["pattern"] in href:
                full_url = "https://www.cmegroup.com" + href if href.startswith('/') else href
                filename = full_url.split('/')[-1]
                
                try:
                    print(f"发现并下载 {key}: {filename}")
                    file_resp = requests.get(full_url, headers=headers, timeout=15)
                    filepath = f"downloads/{filename}"
                    with open(filepath, 'wb') as f:
                        f.write(file_resp.content)
                    
                    target["data"] = {
                        "filename": filename,
                        "url": f"https://raw.githubusercontent.com/{REPO}/main/{filepath}"
                    }
                    target["found"] = True
                except Exception as e:
                    print(f"下载 {key} 失败: {e}")

    if not any(t["found"] for t in targets.values()):
        print("未发现匹配的文件。")
        return

    # 2. 提取日期（优先从 Future 文件名提取，格式通常为 Section62_Metals_Futures_Products_2026-03-24.pdf）
    sample_file = targets["future"]["data"].get("filename") or targets["option"]["data"].get("filename")
    date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', sample_file)
    report_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else datetime.now().strftime("%Y-%m-%d")

    # 3. 构造 Notion 数据包
    # 确保 Name 列显示的是报告日期，方便查看
    new_page_props = {
        "Name": {"title": [{"text": {"content": f"Metals OI_{report_date}"}}]},
        "Date": {"date": {"start": report_date}}
    }

    # 动态添加文件列
    for key, target in targets.items():
        if target["found"]:
            new_page_props[target["notion_col"]] = {
                "files": [
                    {
                        "name": target["data"]["filename"],
                        "type": "external",
                        "external": {"url": target["data"]["url"]}
                    }
                ]
            }

    # 4. 提交到 Notion
    notion = Client(auth=NOTION_TOKEN)
    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=new_page_props)
        print(f"✅ 成功！已将 {report_date} 的期货与期权文件同步至 Notion。")
    except Exception as e:
        print(f"Notion 写入失败: {e}")

if __name__ == "__main__":
    run()
