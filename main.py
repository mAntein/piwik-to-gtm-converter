from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
import json
from datetime import datetime
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/convert")
async def convert_piwik_gtm(file: UploadFile = File(...)):
    piwik_json = json.loads(await file.read())

    # Extract containerVersion once to avoid redundant lookups and extracting correct accountId and containerId
    container_version = piwik_json.get('containerVersion', {})
    account_id = str(container_version.get('accountId', "0"))  # Default to "0" if not found
    container_id = str(container_version.get('containerId', "0"))  # Default to "0" if not found

    # Ensure IDs are numeric, otherwise set default to 0
    if not account_id.isdigit():
        account_id = "0"
    if not container_id.isdigit():
        container_id = "0"

    gtm_json = {
        "exportFormatVersion": 2,
        "exportTime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "containerVersion": {
            "path": f"accounts/{account_id}/containers/{container_id}/versions/0",
            "accountId": account_id,
            "containerId": container_id,
            "containerVersionId": "0",
            "container": {
                "path": f"accounts/{account_id}/containers/{container_id}",
                "accountId": account_id,
                "containerId": container_id,
                "name": "Converted Container",
                "publicId": "GTM-XXXX",
                "usageContext": ["WEB"]
            },
            "tag": [], "trigger": [], "variable": [
                {"name": "Page Hostname", "type": "PAGE_HOSTNAME"},
                {"name": "Page Path", "type": "PAGE_PATH"},
                {"name": "Page URL", "type": "PAGE_URL"},
                {"name": "Referrer", "type": "REFERRER"}
            ], "folder": []
        }
    }

    for index, (tag_id, tag) in enumerate(piwik_json.get('tags', {}).items()):
        gtm_json['containerVersion']['tag'].append({
            "accountId": account_id,
            "containerId": container_id,
            "name": tag['attributes']['name'],
            "type": "html",
            "parameter": [{"type": "TEMPLATE", "key": "html", "value": tag['attributes']['code']}],
            "firingTriggerId": [str(trigger_index + 1) for trigger_index, _ in enumerate(tag.get('triggers', []))],
            "tagId": str(index + 1)
        })

    output_stream = BytesIO()
    output_stream.write(json.dumps(gtm_json, indent=2).encode())
    output_stream.seek(0)

    headers = {'Content-Disposition': 'attachment; filename="converted_gtm.json"'}
    return StreamingResponse(output_stream, media_type='application/json', headers=headers)
