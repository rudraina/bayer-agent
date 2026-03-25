from langchain_core.tools import StructuredTool
from tools import (
    mock_get_logs,
    mock_cicd_pipeline,
    mock_metrics,
)

metrics_tools = [
    StructuredTool.from_function(
        name="get_metrics",
        func=mock_metrics,
        description="Returns simulated system telemetry metrics (CPU, memory, latency, error rate) as a JSON object."
    ),
]

logs_tools = [
    StructuredTool.from_function(
        name="get_logs",
        func=mock_get_logs,
        description="Returns logs within a specified time window around a given ISO 8601 timestamp, simulating a GET API response."
    ),
]

deploy_intelligence_tools = [
    StructuredTool.from_function(
        name="get_cicd_details",
        func=mock_cicd_pipeline,
        description="Returns  CI/CD pipeline execution snapshot with status, stages, timings, and artifact metadata."
    ),
]
