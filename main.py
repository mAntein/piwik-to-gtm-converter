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

    # Automatically extract accountId and containerId from uploaded JSON
    container_version = piwik_json.get('containerVersion', {})
    account_id = container_version.get('accountId', 'UNKNOWN_ACCOUNT')
    container_id = container_version.get('containerId', 'UNKNOWN_CONTAINER')

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
            "tag": [], "trigger": [], "variable": [], "folder": []
        }
    }

    for tag_id, tag in piwik_json.get('tags', {}).items():
        gtm_json['containerVersion']['tag'].append({
            "accountId": account_id,
            "containerId": container_id,
            "name": tag['attributes']['name'],
            "type": "html",
            "parameter": [{"type": "template", "key": "html", "value": tag['attributes']['code']}],
            "firingTriggerId": tag.get('triggers', []),
            "tagId": tag_id
        })

    output_stream = BytesIO()
    output_stream.write(json.dumps(gtm_json, indent=2).encode())
    output_stream.seek(0)

    headers = {'Content-Disposition': 'attachment; filename="converted_gtm.json"'}
    return StreamingResponse(output_stream, media_type='application/json', headers=headers)
