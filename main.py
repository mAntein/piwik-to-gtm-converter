rom fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, HTTPException
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

@app.get("/")
def home():
    return {"message": "Piwik to GTM Converter API is running!"}

# GTM Constants
GTM_EVENT_TYPES = {
    "pageview": "PAGEVIEW",
    "click": "CLICK",
    "form_submit": "FORM_SUBMIT",
    "history_change": "HISTORY_CHANGE",
    "timer": "TIMER"
}

GTM_TAG_FIRING_OPTIONS = {
    "once_per_event": "ONCE_PER_EVENT",
    "once_per_load": "ONCE_PER_LOAD",
    "unlimited": "UNLIMITED"
}

GTM_PARAMETER_TYPES = {
    "TEMPLATE": "TEMPLATE",
    "MAP": "MAP",
    "LIST": "LIST",
    "BOOLEAN": "BOOLEAN",
    "INTEGER": "INTEGER",
    "STRING": "TEMPLATE"
}

@app.post("/convert")
async def convert_piwik_gtm(file: UploadFile = File(...)):
    try:
        piwik_data = json.loads(await file.read())
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON file")

    container_version = piwik_data.get("containerVersion", {})
    account_id = str(container_version.get("accountId", "0"))
    container_id = str(container_version.get("containerId", "0"))

    try:
        account_id = str(int(account_id))
        container_id = str(int(container_id))
    except ValueError:
        account_id = "0"
        container_id = "0"

    gtm_export = {
        "exportFormatVersion": 2,
        "exportTime": datetime.utcnow().isoformat() + "Z",
        "containerVersion": {
            "accountId": account_id,
            "containerId": container_id,
            "containerVersionId": "0",
            "tag": [],
            "trigger": [],
            "variable": [],
            "builtInVariable": [
                {"type": "PAGE_URL"},
                {"type": "PAGE_HOSTNAME"},
                {"type": "PAGE_PATH"},
                {"type": "REFERRER"}
            ]
        }
    }

    trigger_id_map = {}
    for idx, (piwik_trigger_id, piwik_trigger) in enumerate(piwik_data.get("triggers", {}).items(), 1):
        attributes = piwik_trigger.get("attributes", {})
        gtm_trigger = {
            "accountId": account_id,
            "containerId": container_id,
            "triggerId": str(idx),
            "name": attributes.get("name", f"Trigger {idx}"),
            "type": GTM_EVENT_TYPES.get(attributes.get("type", "click"), "CLICK"),
            "filter": []
        }
        gtm_export["containerVersion"]["trigger"].append(gtm_trigger)
        trigger_id_map[piwik_trigger_id] = str(idx)

    for idx, (piwik_tag_id, piwik_tag) in enumerate(piwik_data.get("tags", {}).items(), 1):
        attributes = piwik_tag.get("attributes", {})
        parameters = []
        for param in attributes.get("parameters", []):
            param_type = GTM_PARAMETER_TYPES.get(param.get("type", "TEMPLATE"), "TEMPLATE")
            parameters.append({
                "type": param_type,
                "key": param.get("key", ""),
                "value": param.get("value", "")
            })
        gtm_tag = {
            "accountId": account_id,
            "containerId": container_id,
            "tagId": str(idx),
            "name": attributes.get("name", f"Tag {idx}"),
            "type": "html",
            "parameter": parameters,
            "firingTriggerId": [trigger_id_map.get(t, "1") for t in piwik_tag.get("triggers", []) if t in trigger_id_map],
            "tagFiringOption": GTM_TAG_FIRING_OPTIONS.get("once_per_event", "ONCE_PER_EVENT")
        }
        gtm_export["containerVersion"]["tag"].append(gtm_tag)

    output = BytesIO()
    output.write(json.dumps(gtm_export, indent=2).encode())
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=gtm_export.json"}
    )
