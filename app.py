from fastapi import FastAPI, Request
from graph import agent_graph
from langchain_core.messages import HumanMessage
import os
import json
import logging
import datetime
import sys

app = FastAPI()

# Basic logfmt style logger
logger = logging.getLogger("bayer-agent")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('time="%(asctime)s" level="%(levelname)s" msg="%(message)s"')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

RCA_DIR = os.path.join(os.path.dirname(__file__), "rca_reports")
os.makedirs(RCA_DIR, exist_ok=True)

@app.get("/health")
def health():
    return {"status": "ok"}

def generate_rca_markdown(incident: dict, responses: list) -> str:
    incident_id = incident.get("incident_id", "unknown_incident")
    
    md_parts = []
    md_parts.append(f"# Root Cause Analysis: {incident_id}")
    md_parts.append(f"**Generated at:** {datetime.datetime.utcnow().isoformat()}Z\n")
    
    md_parts.append("## Incident Summary")
    md_parts.append("```json")
    md_parts.append(json.dumps(incident, indent=2))
    md_parts.append("```\n")
    
    md_parts.append("## Agent Train of Thought")
    md_parts.append("> *The following outlines the reasoning and delegation steps taken by the diagnostic orchestrator to reach its conclusion.*\n")
    
    # Exclude the final response as it represents the final resolution
    investigation_steps = responses[:-1]
    
    for i, step in enumerate(investigation_steps, 1):
        md_parts.append(f"### Step {i}")
        md_parts.append(f"{step}\n")
        
    md_parts.append("## Final Resolution")
    final_resolution = responses[-1] if responses else "No resolution found."
    md_parts.append(f"{final_resolution}\n")
    
    return "\n".join(md_parts)

@app.post("/trigger")
async def trigger_pipeline(request: Request):
    try:
        incident = await request.json()
    except Exception:
        # fallback to payload.json
        payload_path = os.path.join(os.path.dirname(__file__), "data", "payload.json")
        if os.path.exists(payload_path):
            with open(payload_path, "r") as f:
                incident = json.load(f)
        else:
            incident = {}
            
    incident_id = incident.get("incident_id", "unknown")
    logger.info(f"incident_received incident_id='{incident_id}'")
    
    state = {
        "messages": [HumanMessage(content="An incident has occurred. Find the details required and provide its resolution with proper reasoning. The incident is: " + str(incident))],
        "next_agent": None,
        "next_agent_instructions": ""
    }

    result = await agent_graph.ainvoke(state)
    logger.info("incident_analysis_completed")
    
    # Extract AI responses
    responses = [m.content for m in result.get("messages", []) if m.type == "ai"]
    
    final_resolution = responses[-1] if responses else "No resolution found"
    
    # Generate the Markdown Artifact
    rca_markdown = generate_rca_markdown(incident, responses)
    
    # Write to local file
    output_file = os.path.join(RCA_DIR, f"rca_{incident_id}.md")
    with open(output_file, "w") as f:
        f.write(rca_markdown)
        
    logger.info(f"rca_generated file='{output_file}'")
    
    return {
        "incident_id": incident_id,
        "status": "success",
        "resolution": final_resolution,
        "rca_markdown": rca_markdown,
        "full_trace": responses
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)