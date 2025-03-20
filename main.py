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

    # Extract accountId and containerId safely
    container_version = piwik_json.get('containerVersion', {})
    account_id = str(container_version.get('accountId', "0"))
    container_id = str(container_version.get('containerId', "0"))

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
            "tag": [],
            "trigger": [],
            "variable": [
                {"name": "Page Hostname", "type": "PAGE_HOSTNAME"},
                {"name": "Page Path", "type": "PAGE_PATH"},
                {"name": "Page URL", "type": "PAGE_URL"},
                {"name": "Referrer", "type": "REFERRER"}
            ],
            "folder": []
        }
    }

    event_type_mapping = {
        "page_view": "page_view",
        "click": "click",
        "form_submit": "form_submission",
        "history_change": "history_change",
        "timer": "timer",
        "custom_event": "trigger_group"
    }

    # Convert Piwik triggers to GTM triggers
    trigger_mapping = {}
    for trigger_index, (trigger_id, trigger) in enumerate(piwik_json.get('triggers', {}).items(), start=1):
        trigger_name = trigger.get('attributes', {}).get('name', f"Trigger {trigger_index}")
        piwik_event_type = trigger.get("attributes", {}).get("type", "custom_event")
        gtm_event_type = event_type_mapping.get(piwik_event_type, "trigger_group")

        gtm_trigger = {
            "accountId": account_id,
            "containerId": container_id,
            "triggerId": str(trigger_index),
            "name": trigger_name,
            "type": gtm_event_type,
            "filter": []
        }

        gtm_json['containerVersion']['trigger'].append(gtm_trigger)
        trigger_mapping[trigger_id] = str(trigger_index)

    # Convert Piwik tags to GTM tags
    for tag_index, (tag_id, tag) in enumerate(piwik_json.get('tags', {}).items(), start=1):
        tag_name = tag['attributes'].get('name', f"Tag {tag_index}")
        tag_code = tag['attributes'].get('code', '')

        # Map Piwik triggers to GTM firing triggers
        piwik_trigger_ids = tag.get('triggers', [])
        gtm_firing_triggers = [trigger_mapping.get(tid, "1") for tid in piwik_trigger_ids if tid in trigger_mapping]

        gtm_tag = {
            "accountId": account_id,
            "containerId": container_id,
            "tagId": str(tag_index),
            "name": tag_name,
            "type": "html",
            "parameter": [{"type": "TEMPLATE", "key": "html", "value": tag_code}],
            "firingTriggerId": gtm_firing_triggers
        }

        gtm_json['containerVersion']['tag'].append(gtm_tag)

    output_stream = BytesIO()
    output_stream.write(json.dumps(gtm_json, indent=2).encode())
    output_stream.seek(0)

    headers = {'Content-Disposition': 'attachment; filename="converted_gtm.json"'}
    return StreamingResponse(output_stream, media_type='application/json', headers=headers)
