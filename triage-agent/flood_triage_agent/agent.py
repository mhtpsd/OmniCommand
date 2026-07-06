"""
flood_triage_agent/agent.py
-----------------------------
This is the piece that genuinely earns the "Gemini Enterprise Agent
Platform" rubric item -- the triage logic runs as an ADK Agent through
Google's Agent Platform runtime, instead of a bare google-genai API call.

ADK looks for a module-level `root_agent` variable in this file -- don't
rename it. The folder name `flood_triage_agent` becomes the "app name"
used in the API server's URLs (see ADD_GEMINI_AGENT_PLATFORM.md).
"""

from google.adk.agents import Agent

INSTRUCTION = """You are an urban hazard triage assistant supporting an
emergency response dashboard. Given a photo of a possible hazard
(flooding, downed power line, road blockage, or other), identify the
hazard type. If flooding, estimate water depth in meters using visible
reference objects (car doors, curbs, people) as scale. Give a
one-sentence recommendation for a human dispatcher to review -- phrase
it as a suggestion for a person to confirm, never as an automatic
action. Respond ONLY with JSON, no markdown fences, in exactly this
shape:
{"hazard_type": string, "estimated_water_depth_m": number or null,
"recommendation": string, "confidence": "low"|"medium"|"high"}"""

# Verify current model availability before your final demo run -- as of
# mid-2026, gemini-2.5-flash (fast/cheap) or gemini-3.1-pro (higher
# accuracy on complex scenes) are reasonable choices.
root_agent = Agent(
    name="flood_triage_agent",
    model="gemini-2.5-flash",
    description="Analyzes citizen-submitted hazard photos for emergency dispatch triage.",
    instruction=INSTRUCTION,
)
