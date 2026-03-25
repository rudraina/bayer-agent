import logging
from typing import List, TypedDict, Optional
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

logger = logging.getLogger("bayer-agent")
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import create_react_agent

from tools_config import metrics_tools, logs_tools, deploy_intelligence_tools
from llms import supervisor_llm, logs_llm, metrics_llm, deploy_intelligence_llm
from utils import extract_json
from typing import TypedDict, Any, Dict, List, Optional


# =====================================================================================
#   STATE MODEL (supports merge/reducers)
# =====================================================================================


class AgentState(MessagesState):
    """
    State structure for graph.
    - `messages` auto-merges (append) because it's part of MessagesState.
    - other keys overwrite.
    """
    next_agent: Optional[str]
    next_agent_instructions: Optional[str]


# =====================================================================================
#   REACT AGENTS WITH FULL PROMPTS
# =====================================================================================
# ---------------------------
# SUPERVISOR / ROUTER AGENT
# ---------------------------
router_agent = create_react_agent(
    model=supervisor_llm,
    tools=[],
    name="router",
    prompt = 

"""
You are the SUPERVISOR agent. Your job is to route user messages to the correct sub-agent and ensure that the user's query is fully addressed.Do not ask for additional data,make decisions based on the available data.

=========================
            RULES
=========================

1. Understand the incident in detail. Try getting an initial idea about the incident and it's cause and the 'trigger_time'.Ask sub agents to only consider the info that falls in the range (15 minutes before and after the 'trigger_time' of the incident).

2. After any sub-agent responds, carefully read the last message from that sub-agent and understand exactly what has been completed. Update the current state accordingly.

3. Before deciding what to do next, REASON SLOWLY AND CAREFULLY about:
   - Why the incident occured,
   - What information or actions have already been handled by sub-agents,
   - What gaps or remaining tasks still exist.

4. Determine whether the incident's full analysics/debugging has been completely resolved:
   - If yes, produce a final summary that clearly and thoroughly explains the resolution to the incident. This summary must not merely state that tasks are completed, but must communicate the actual information, results, and outcomes relevant to the incident.
     
     Output:
     {
       "next_agent": "end",
       "next_agent_instructions": "<detailed final summary explaining the full root cause artifact,resolution and reasoning for it.>"
     }

   - If no, delegate the remaining tasks to the correct sub-agent with precise, actionable instructions.



5. Always output valid JSON in the following structure:
   {
     "next_agent": "<logs_agent | metrics_agent | deploy_intelligence_agent | end>",
     "next_agent_instructions": "<instructions OR detailed final summary>"
   }

6. Never output anything besides JSON.

7. Never invent information.

8. Be specific, explicit, and actionable when delegating tasks to sub-agents.

9. Sub-agents available:
Logs Agent (forensic)
- Finds errors, stack traces, cross-service correlations
- Use for runtime failures or unclear issues

Metrics Agent (telemetry)
- Detects anomalies (CPU, memory, latency p95/p99)
- Use for threshold alerts or performance issues

Deploy Intelligence Agent (historian)
- Maps issues to deployments/config/feature flags
- Use for recent changes or suspected config bugs (default bias)

10.If a sub-agent has been caled before, do not call it back again.
"""
)

# ---------------------------
# logs AGENT
# ---------------------------
logs_agent = create_react_agent(
    model=logs_llm,
    tools=logs_tools,
    name="logs_agent",
    prompt=

"""
You are the Logs Agent (Forensic Expert).

=========================
            RULES
=========================

1. Analyze distributed application logs to identify:
- Errors, exceptions, stack traces
- Cross-service correlations
- Hidden failure patterns

2. ALWAYS call the appropriate log tool for any log-related request.Ensure that you analyze the logs based on 'analysis_window' start and end timings.

3. Wait for all tool responses before producing your final JSON.

4. You may use internal reasoning, but DO NOT output it.

5. After completing all tool calls,only consider the data that is in range (15 minutes before the incident trigger_time,15 minutes after the incident trigger_time) respond ONLY with valid JSON:

{
  "next_agent": "router_agent",
  "next_agent_instructions": "<summary of what was done / results>"
}

6. Summaries must:
   - Clearly describe tool results
   - Specify missing data or next steps

7. Never guess or invent logs.

=========================
"""
)


# ---------------------------
# metrics AGENT
# ---------------------------
metrics_agent = create_react_agent(
    model=metrics_llm,
    tools=metrics_tools,
    name="metrics_agent",
    prompt=

"""
You are the Metrics Agent (Telemetry Analyst).

=========================
            RULES
=========================

1.Analyze system metrics to detect:
- Anomalies
- Performance degradation
- Resource saturation patterns

2. ALWAYS call the appropriate metric tool for any metric-related request.

3. Wait for all tool responses before producing your final JSON.

4. You may use internal reasoning, but DO NOT output it.

5. After completing all tool calls,only consider the data that is in range (15 minutes before the incident trigger_time,15 minutes after the incident trigger_time) for analyzing and  respond ONLY with valid JSON:

{
  "next_agent": "router_agent",
  "next_agent_instructions": "<summary of what was done / results>"
}

6. Summaries must:
   - Clearly describe tool results
   - Specify missing data or next steps

7. Never guess or invent metrics.

=========================
"""

)


# ---------------------------
# deploy_intelligence AGENT
# ---------------------------
deploy_intelligence_agent = create_react_agent(
    model=deploy_intelligence_llm,
    tools=deploy_intelligence_tools,
    name="deploy_intelligence_agent",
    prompt=

"""
You are the Deploy Intelligence Agent (Historian).

=========================
            RULES
=========================

1. Correlate system issues with:
- CI/CD deployments
- Configuration changes
- Feature flag rollouts

2. ALWAYS call the appropriate tool for any cicd-related request.

3. Wait for all tool responses before producing your final JSON.

4. You may use internal reasoning, but DO NOT output it.

5. After completing all tool calls,only consider the data that is in range (15 minutes before the incident trigger_time,15 minutes after the incident trigger_time)and respond ONLY with valid JSON:

{
  "next_agent": "router_agent",
  "next_agent_instructions": "<summary of what was done / results>"
}

6. Summaries must:
   - Clearly describe tool results
   - Specify missing data or next steps

7. Never guess or invent deployment details .
=========================
"""
)
# =====================================================================================
#   COMMON AGENT EXECUTION HELPER
# =====================================================================================

async def run_agent(agent, state: AgentState):
    """
    Unified helper for invoking an agent safely.
    """

    res = await agent.ainvoke({"messages": state["messages"]})


    last_ai = next(
        (m for m in reversed(res["messages"]) if isinstance(m, AIMessage)),
        None
    )
    if not last_ai:
        raise RuntimeError(f"{agent.name} did not produce an AIMessage.")

    logger.info(f"agent_response agent='{agent.name}' content='{last_ai.content.replace(chr(10), ' ')}'")
    
    parsed = extract_json(last_ai.content)
    
    next_agent = parsed.get("next_agent", "end")
    # Normalize: lowercase and replace spaces with underscores to match node IDs
    if isinstance(next_agent, str):
        next_agent = next_agent.lower().replace(" ", "_").strip()
        
    instructions = parsed.get("next_agent_instructions", "")
    
    # Safely truncate instructions for the log to stay readable
    preview = str(instructions).replace('\n', ' ')
    if len(preview) > 100:
        preview = preview[:97] + "..."
        
    logger.info(f"agent_handoff source_agent='{agent.name}' target_agent='{next_agent}' instructions_preview='{preview}'")

    return next_agent, instructions


# =====================================================================================
#   NODE DEFINITIONS
# =====================================================================================

async def router_node(state: AgentState) -> AgentState:
    next_agent, instructions = await run_agent(router_agent, state)
    return {
        "next_agent": next_agent,
        "next_agent_instructions": instructions,
        "messages": [AIMessage(content=instructions)],

    }


async def logs_node(state: AgentState) -> AgentState:
    next_agent, instructions = await run_agent(logs_agent, state)
    return {
        "next_agent": next_agent,
        "next_agent_instructions": instructions,
        "messages": [AIMessage(content=instructions)],

    }


async def metrics_node(state: AgentState) -> AgentState:
    next_agent, instructions = await run_agent(metrics_agent, state)
    return {
        "next_agent": next_agent,
        "next_agent_instructions": instructions,
        "messages": [AIMessage(content=instructions)],

    }


async def deploy_intelligence_node(state: AgentState) -> AgentState:
    next_agent, instructions = await run_agent(deploy_intelligence_agent, state)
    return {
        "next_agent": next_agent,
        "next_agent_instructions": instructions,
        "messages": [AIMessage(content=instructions)],

    }


# =====================================================================================
#   GRAPH ASSEMBLY
# =====================================================================================

def build_traditional_graph():
    graph = StateGraph(AgentState)

    graph.set_entry_point("router")

    graph.add_node("router", router_node)
    graph.add_node("logs_agent", logs_node)
    graph.add_node("metrics_agent", metrics_node)
    graph.add_node("deploy_intelligence_agent", deploy_intelligence_node)

    graph.add_conditional_edges(
        "router",
        lambda state: state.get("next_agent"),
        {
            "logs_agent": "logs_agent",
            "metrics_agent": "metrics_agent",
            "deploy_intelligence_agent": "deploy_intelligence_agent",
            "end": END,
        }
    )

    graph.add_edge("logs_agent", "router")
    graph.add_edge("metrics_agent", "router")
    graph.add_edge("deploy_intelligence_agent", "router")

    graph.set_finish_point("router")

    return graph.compile()


# =====================================================================================
#   EXPORTED GRAPH
# =====================================================================================

agent_graph = build_traditional_graph()