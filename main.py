import os
import requests
from datetime import datetime
from notion_client import Client

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
REPO = os.getenv("GITHUB_REPOSITORY")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

def run():
    os.makedirs("downloads", exist_ok=True)
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    # 直接硬编码直达网址，配合自定义文件名保存
    targets = {
        "future": {
            "url": "https://www.cmegroup.com/daily_bulletin/current/Section62_Metals_Futures_Products.pdf",
            "notion_col": "File",
            "filename": f"Section62_Metals_Futures_{report_date}.pdf",
            "found": False
        },
        "option": {
            "url": "https://www.cmegroup.com/daily_bulletin/current/Section64_Metals_Option_Products.pdf",
            "notion_col": "Option File",
            "filename": f"Section64_Metals_Option_{report_date}.pdf",
            "found": False
        }
    }

    print("开始通过 ScraperAPI 绕过防火墙下载...")
    for key, target in targets.items():
        # 将目标 URL 拼接到 ScraperAPI 的接口上
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={target['url']}"
        print(f"正在请求 {key} 文件...")
        
        try:
            # 代理抓取可能需要一点时间，设置 60 秒超时
            resp = requests.get(api_url, timeout=60)
            if resp.status_code == 200:
                filepath = f"downloads/{target['filename']}"
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                
                target["final_url"] = f"https://raw.githubusercontent.com/{REPO}/main/{filepath}"
                target["found"] = True
                print(f"✅ {key} 下载成功！已存为 {target['filename']}")
            else:
                print(f"❌ {key} 下载失败，ScraperAPI 返回状态码: {resp.status_code}")
        except Exception as e:
            print(f"❌ 请求过程出错: {e}")

    if not any(t["found"] for t in targets.values()):
        print("未能下载任何文件，流程终止。")
        return

    print("正在生成 Notion 记录...")
    properties = {
        "Name": {"title": [{"text": {"content": f"Metals OI_{report_date}"}}]},
        "Date": {"date": {"start": report_date}}
    }

    for key, target in targets.items():
        if target["found"]:
            properties[target["notion_col"]] = {
                "files": [{"name": target["filename"], "type": "external", "external": {"url": target["final_url"]}}]
            }

    notion = Client(auth=NOTION_TOKEN)
    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=properties)
        print("🎉 Notion 数据库同步完毕！")
    except Exception as e:
        print(f"写入 Notion 时出错: {e}")

if __name__ == "__main__":
    run()
