import os
import requests
import json
from datetime import datetime
from notion_client import Client
from cme_parsers.oi_section62 import parse_section62
from cme_parsers.oi_section64 import parse_section64

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
                target["filepath"] = filepath
                target["found"] = True
                print(f"✅ {key} 下载成功！已存为 {target['filename']}")
            else:
                print(f"❌ {key} 下载失败，ScraperAPI 返回状态码: {resp.status_code}")
        except Exception as e:
            print(f"❌ 请求过程出错: {e}")

    # 解析文件
    parse_status = "OK"
    futures_json = None
    options_json = None
    TARGET_FUT = {"GC", "SI", "PL", "PA", "HG", "MGC", "SIL", "MHG", "QO", "QI", "SIC"}
    TARGET_OPT_PREFIXES = ("OG", "SO", "PO")

    # 1. 解析 Future PDF (Section 62)
    if targets["future"]["found"]:
        try:
            print("Parsing future PDF...")
            future_data = parse_section62(targets["future"]["filepath"])
            
            # 过滤贵金属和铜，并检查 status
            filtered_futures = {}
            for code in TARGET_FUT:
                if code in future_data:
                    c_data = future_data[code]
                    filtered_futures[code] = {
                        "name": c_data.get("name"),
                        "total_oi": c_data.get("total_oi"),
                        "total_oi_chg": c_data.get("total_oi_chg"),
                        "months": c_data.get("months", [])
                    }
                    c_status = c_data.get("status", "")
                    if c_status != "OK" and not c_status.startswith("NO_TOTAL"):
                        parse_status = f"FUT_PARSE_FAILED ({code}): {c_status}"
            
            futures_json = json.dumps(filtered_futures, ensure_ascii=False, separators=(',', ':'))[:1900]
        except Exception as ex:
            parse_status = f"FUT_PARSE_ERROR: {str(ex)}"
    else:
        parse_status = "FUTURE_DOWNLOAD_FAILED"

    # 2. 解析 Option PDF (Section 64)
    if parse_status == "OK" or parse_status.startswith("FUT_PARSE_FAILED"):
        if targets["option"]["found"]:
            try:
                print("Parsing option PDF...")
                option_data = parse_section64(targets["option"]["filepath"])
                
                # 过滤出键名以 TARGET_OPT_PREFIXES 中的前缀开头的商品
                filtered_options = {}
                for k, v in option_data.items():
                    if any(k.startswith(p + "_") for p in TARGET_OPT_PREFIXES):
                        filtered_options[k] = v
                
                options_json = json.dumps(filtered_options, ensure_ascii=False, separators=(',', ':'))[:1900]
            except Exception as ex:
                if parse_status == "OK":
                    parse_status = f"OPT_PARSE_ERROR: {str(ex)}"
        else:
            if parse_status == "OK":
                parse_status = "OPTION_DOWNLOAD_FAILED"

    if not any(t["found"] for t in targets.values()):
        print("未能下载任何文件，流程终止。")
        return

    print("正在生成 Notion 记录...")
    properties = {
        "Name": {"title": [{"text": {"content": f"Metals OI_{report_date}"}}]},
        "Date": {"date": {"start": report_date}},
        "Parse Status": {"rich_text": [{"text": {"content": parse_status[:1900]}}]}
    }

    for key, target in targets.items():
        if target["found"]:
            properties[target["notion_col"]] = {
                "files": [{"name": target["filename"], "type": "external", "external": {"url": target["final_url"]}}]
            }

    # 当且仅当状态为 OK 时，回填结构化 JSON (失败时 omit 这些字段)
    if parse_status == "OK" and futures_json is not None and options_json is not None:
        properties.update({
            "OI Futures (JSON)": {"rich_text": [{"text": {"content": futures_json}}]},
            "OI Options (JSON)": {"rich_text": [{"text": {"content": options_json}}]}
        })

    notion = Client(auth=NOTION_TOKEN)
    try:
        # 查重按 Date 过滤
        query_res = notion.databases.query(
            database_id=DATABASE_ID,
            filter={
                "property": "Date",
                "date": {
                    "equals": report_date
                }
            }
        )
        results = query_res.get("results", [])
        if results:
            page_id = results[0]["id"]
            notion.pages.update(page_id=page_id, properties=properties)
            print("🎉 Notion 数据库已存在对应日期的记录，更新成功！")
        else:
            notion.pages.create(parent={"database_id": DATABASE_ID}, properties=properties)
            print("🎉 Notion 数据库同步完毕（新建记录）！")
    except Exception as e:
        print(f"写入 Notion 时出错: {e}")

if __name__ == "__main__":
    run()

