from fastapi.middleware.cors import CORSMiddleware
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

# GTM Constants
GTM_EVENT_TYPES = {
    "pageview": "pageView",
    "click": "click",
    "submit": "formSubmit",
    "history_change": "historyChange",
    "custom_event": "customEvent"
}

GTM_VARIABLE_TYPES = {
    "text": "v",
    "url": "u",
    "data_layer": "d"
}

def map_piwik_condition_to_gtm_filter(piwik_condition: dict) -> dict:
    """Convert Piwik Pro trigger conditions to GTM filters."""
    # Example Piwik condition: {"type": "url_contains", "value": "checkout"}
    # GTM filter format: https://developers.google.com/tag-manager/api/v2/reference/accounts/containers/workspaces/triggers
    condition_type = piwik_condition.get("type", "")
    value = piwik_condition.get("value", "")
    
    if condition_type == "url_contains":
        return {
            "type": "CONTAINS",
            "parameter": [
                {"type": "TEMPLATE", "key": "arg0", "value": "{{Page URL}}"},
                {"type": "TEMPLATE", "key": "arg1", "value": value}
            ]
        }
    # Add more mappings as needed
    return {}

def convert_piwik_variable(piwik_var: dict) -> dict:
    """Convert Piwik Pro variables to GTM variables."""
    return {
        "name": piwik_var.get("name", ""),
        "type": "gas",
        "parameter": [
            {"type": "TEMPLATE", "key": "name", "value": piwik_var.get("name", "")},
            {"type": "TEMPLATE", "key": "value", "value": piwik_var.get("value", "")}
        ]
    }

@app.post("/convert")
async def convert_piwik_gtm(file: UploadFile = File(...)):
    try:
        piwik_data = json.loads(await file.read())
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON file")

    # Extract container version details
    container_version = piwik_data.get("containerVersion", {})
    account_id = container_version.get("accountId", "0")
    container_id = container_version.get("containerId", "0")

    # Validate IDs (GTM requires numeric values)
    try:
        account_id = str(int(account_id))
        container_id = str(int(container_id))
    except ValueError:
        account_id = "0"
        container_id = "0"

    # Base GTM structure (matches API v2)
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
            "fingerprint": "",
            "tagManagerUrl": "",
            "name": "Converted from Piwik Pro",
            "description": "",
            "builtInVariable": [
                {"type": "PAGE_URL"},
                {"type": "PAGE_HOSTNAME"},
                {"type": "PAGE_PATH"},
                {"type": "REFERRER"}
            ]
        }
    }

    # Convert Triggers (Piwik Pro -> GTM)
    trigger_id_map = {}
    for idx, (piwik_trigger_id, piwik_trigger) in enumerate(piwik_data.get("triggers", {}).items(), 1):
        attributes = piwik_trigger.get("attributes", {})
        
        gtm_trigger = {
            "accountId": account_id,
            "containerId": container_id,
            "triggerId": str(idx),
            "name": attributes.get("name", f"Trigger {idx}"),
            "type": GTM_EVENT_TYPES.get(attributes.get("type", "pageview"), "pageView"),
            "filter": [],
            "customEventFilter": [],
            "autoEventFilter": []
        }

        # Map Piwik conditions to GTM filters
        for condition in piwik_trigger.get("conditions", []):
            if gtm_filter := map_piwik_condition_to_gtm_filter(condition):
                gtm_trigger["filter"].append(gtm_filter)

        gtm_export["containerVersion"]["trigger"].append(gtm_trigger)
        trigger_id_map[piwik_trigger_id] = str(idx)

    for idx, (piwik_tag_id, piwik_tag) in enumerate(piwik_data.get("tags", {}).items(), 1):
        attributes = piwik_tag.get("attributes", {})
        
        gtm_tag = {
            "accountId": account_id,
            "containerId": container_id,
            "tagId": str(idx),
            "name": attributes.get("name", f"Tag {idx}"),
            "type": "html",
            "parameter": [
                {"type": "TEMPLATE", "key": "html", "value": attributes.get("code", "")}
            ],
            "firingTriggerId": [trigger_id_map[t] for t in piwik_tag.get("triggers", []) if t in trigger_id_map],
            "tagFiringOption": "oncePerEvent",
            "monitoringMetadata": {"type": "map"}
        }

        gtm_export["containerVersion"]["tag"].append(gtm_tag)

    # Convert Variables
    for piwik_var in piwik_data.get("variables", []):
        if gtm_var := convert_piwik_variable(piwik_var):
            gtm_export["containerVersion"]["variable"].append(gtm_var)

    # Prepare downloadable JSON
    output = BytesIO()
    output.write(json.dumps(gtm_export, indent=2).encode())
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=gtm_export.json"}
    )
