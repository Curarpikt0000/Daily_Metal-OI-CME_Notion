import os
import sys
from notion_client import Client

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID") or "2fc47eb5fd3c8035ab22cabf3e6e41bb"

if not NOTION_TOKEN:
    print("Error: NOTION_TOKEN not set in environment.")
    sys.exit(1)

notion = Client(auth=NOTION_TOKEN)

try:
    print(f"Querying pages for 2026-05-29 in database: {DATABASE_ID}...")
    res = notion.databases.query(
        database_id=DATABASE_ID,
        filter={
            "property": "Date",
            "date": {
                "equals": "2026-05-29"
            }
        }
    )
    results = res.get("results", [])
    print(f"Found {len(results)} pages for 2026-05-29:")
    
    pages_with_data = []
    pages_without_data = []
    
    for page in results:
        page_id = page["id"]
        props = page.get("properties", {})
        
        # Check if page has JSON data in "OI Futures (JSON)" or "OI Options (JSON)"
        fut_rt = props.get("OI Futures (JSON)", {}).get("rich_text", [])
        fut_content = "".join([t.get("text", {}).get("content", "") for t in fut_rt])
        
        opt_rt = props.get("OI Options (JSON)", {}).get("rich_text", [])
        opt_content = "".join([t.get("text", {}).get("content", "") for t in opt_rt])
        
        created_time = page.get("created_time")
        
        print(f" - Page ID: {page_id} | Created: {created_time} | Futures JSON len: {len(fut_content)} | Options JSON len: {len(opt_content)}")
        
        # If it has actual JSON structure (not empty)
        if len(fut_content) > 5 and len(opt_content) > 5:
            pages_with_data.append((page_id, created_time))
        else:
            pages_without_data.append((page_id, created_time))
            
    # Cleanup empty ones
    for pid, ctime in pages_without_data:
        print(f"Archiving empty duplicate page: {pid} (Created: {ctime}) ...")
        notion.pages.update(page_id=pid, archived=True)
        print("Archived successfully.")
        
    # If there are multiple populated ones, keep the latest one (first in the list usually)
    if len(pages_with_data) > 1:
        # Sort by creation time descending (newest first)
        pages_with_data.sort(key=lambda x: x[1], reverse=True)
        # Keep pages_with_data[0], archive the rest
        for pid, ctime in pages_with_data[1:]:
            print(f"Archiving older populated duplicate page: {pid} (Created: {ctime}) ...")
            notion.pages.update(page_id=pid, archived=True)
            print("Archived successfully.")
            
    print("Cleanup run finished!")
except Exception as e:
    print(f"Error during cleanup: {e}")
