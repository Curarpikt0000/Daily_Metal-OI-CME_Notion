import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from notion_client import Client

# 读取 GitHub Secrets 里的环境变量
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
REPO = os.getenv("GITHUB_REPOSITORY") # 获取你的仓库名，例如 Curarpikt0000/OI-CME-download-

CME_URL = "https://www.cmegroup.com/market-data/daily-bulletin.html"

def run():
    # 1. 模拟浏览器访问 CME 网页
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    print("正在访问 CME 网站...")
    try:
        response = requests.get(CME_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"访问 CME 网站失败，可能被防爬虫拦截: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # 2. 寻找包含 PG 62 或 Section62 的文件链接
    file_url = None
    for a in soup.find_all('a', href=True):
        if 'Section62' in a['href'] or 'PG 62' in a.text:
            file_url = a['href']
            # 如果是相对路径，拼凑成绝对路径
            if file_url.startswith('/'):
                file_url = "https://www.cmegroup.com" + file_url
            break

    if not file_url:
        print("未能在网页上找到 Metals Futures Products - PG 62 的链接。")
        return

    print(f"找到文件链接: {file_url}")

    # 3. 下载文件
    filename = file_url.split('/')[-1]
    print("正在下载文件...")
    try:
        file_resp = requests.get(file_url, headers=headers, timeout=15)
        file_resp.raise_for_status()
    except Exception as e:
        print(f"下载文件失败: {e}")
        return

    # 创建一个 downloads 文件夹用来存放文件
    os.makedirs("downloads", exist_ok=True)
    filepath = f"downloads/{filename}"

    with open(filepath, 'wb') as f:
        f.write(file_resp.content)
    print(f"文件已下载到: {filepath}")

    # 4. 从文件名提取日期 (匹配 YYYYMMDD 或 YYYY-MM-DD)
    date_match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', filename)
    if date_match:
        report_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    else:
        # 如果文件名没有明显日期，默认使用当天的日期
        report_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"提取到的日期: {report_date}")

    # 5. 构造 GitHub 的公开下载链接供 Notion 使用
    raw_github_url = f"https://raw.githubusercontent.com/{REPO}/main/{filepath}"

    # 6. 更新你的 Notion Database
    print("正在写入 Notion...")
    notion = Client(auth=NOTION_TOKEN)
    
    new_page = {
        "Name": {"title": [{"text": {"content": filename}}]},  # 第一列 Name
        "Date": {"date": {"start": report_date}},              # 日期列 Date
        "File": {
            "files": [
                {
                    "name": filename, 
                    "type": "external", 
                    "external": {"url": raw_github_url}        # 外部链接 File
                }
            ]
        }
    }

    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=new_page)
        print("🎉 成功添加到 Notion！")
    except Exception as e:
        print(f"写入 Notion 时出错: {e}")

# ================= 注意这里！完全靠左对齐！ =================
if __name__ == "__main__":
    run()
