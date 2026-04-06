"""
Vulcan OmniPro 220 Agent using the Anthropic API with tool use.
Provides structured tools for querying the manual knowledge base
and generating visual artifacts.
"""

import json
import base64
from pathlib import Path
from anthropic import Anthropic
from backend.knowledge import (
    search_manual,
    get_manual_page,
    get_duty_cycle,
    get_troubleshooting,
    get_polarity,
    get_specifications,
    get_selection_chart,
)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

SYSTEM_PROMPT = """You are the Vulcan OmniPro 220 Expert Assistant. You help people set up, operate, troubleshoot, and maintain their Vulcan OmniPro 220 multiprocess welding system.

PERSONALITY:
- You're a knowledgeable shop buddy, not a manual search engine
- Assume the user is in their garage, hands possibly dirty, looking at their welder
- Be direct and practical. Lead with what to DO, then explain why
- If something is a safety concern, flag it immediately even if they didn't ask

CONVERSATION STATE:
Track and remember these across the conversation:
- Input voltage (120V or 240V)
- Welding process (MIG, Flux-Core, TIG, Stick)
- Wire type and diameter
- Material being welded
- Material thickness
Use accumulated context to adjust all subsequent answers. When the user mentions any of these, remember them for future questions.

ANSWERING RULES:
1. Only state specs/facts that appear in the owner's manual, quick start guide, or selection chart. Never invent capabilities this machine may not have.
2. Always cite your source: "Per page X of the owner's manual..." or "From the duty cycle table on page 29..."
3. If the manual doesn't cover something, say so clearly. Offer the Harbor Freight support number: 1-800-444-3353
4. If a question is ambiguous, ask ONE focused clarifying question before guessing.

VERIFIED POLARITY FACTS (hardcoded, always use these — do NOT rely on tool retrieval for polarity):
- MIG welding: DCEP (electrode positive). Ground clamp → Negative (-) socket, MIG gun wire feed → Positive (+) socket
- Flux-Core welding: DCEN (electrode negative). Ground clamp → Positive (+) socket, MIG gun wire feed → Negative (-) socket
- TIG welding: DCEN (electrode negative). Ground clamp → Positive (+) socket, TIG torch → Negative (-) socket
- Stick welding: DCEP or DCEN depending on electrode type (check electrode packaging)

SAFETY-FIRST:
If the user's described setup has any safety concern — wrong polarity, inadequate circuit rating, missing ground, improper gas setup — flag it IMMEDIATELY, even if they didn't ask about safety. Safety warnings always come first in your response.

VISUAL RESPONSE JUDGMENT — USE render_artifact WHEN:
- Polarity/wiring question → SVG diagram showing which cable goes in which socket on the front panel
- Duty cycle question → interactive HTML table with the relevant cell highlighted
- Settings across multiple variables → interactive calculator or comparison table
- "How do I set up X" → step-by-step with a diagram at the key physical setup step
- Troubleshooting with multiple diagnostic paths → flowchart
- DO NOT use render_artifact for simple yes/no or single-fact answers

When generating artifacts:
- Use self-contained HTML with inline CSS and JS (no external dependencies)
- Make them visually clean with the Vulcan red (#CC0000) as accent color
- Ensure all text is readable and all interactive elements work
- For SVG diagrams, use clear labels and arrows

CONFIDENCE SIGNALING:
- When citing hardcoded facts or direct manual quotes: state confidently with page reference
- When interpreting symptoms or diagnosing from photos: signal uncertainty, suggest confirmation steps
- When outside manual scope: say so explicitly, never blend general welding knowledge with this machine's specific specs unless clearly labeled as "General welding note:"

MULTI-STEP REASONING:
For complex questions, use MULTIPLE tools before answering. Example: "porosity at 180A"
→ call get_troubleshooting("porosity") AND get_duty_cycle("MIG", "240V", 180) AND search_manual("porosity"). Cross-reference all results before giving your answer.

WHEN USER UPLOADS AN IMAGE:
Analyze the image carefully. If it shows a weld, diagnose the quality (look for porosity, undercut, spatter, cold lap, burn-through, proper penetration). Cross-reference with the troubleshooting data using get_troubleshooting. If it shows the welder or setup, identify what's visible and offer guidance.
"""

TOOLS = [
    {
        "name": "search_manual",
        "description": "Search the Vulcan OmniPro 220 owner's manual knowledge base by topic or keyword. Returns relevant sections with page references. Use this for general questions about the welder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g., 'wire feed tension', 'gas setup', 'aluminum welding')"
                },
                "process_filter": {
                    "type": "string",
                    "enum": ["MIG", "Flux-Core", "TIG", "Stick"],
                    "description": "Optional: filter results to a specific welding process"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_manual_page",
        "description": "Get the full extracted content and original image URL for a specific manual page (1-48). Use when you need to see a specific diagram, table, or schematic in detail, or when you want to reference a specific page image.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_number": {
                    "type": "integer",
                    "description": "Page number (1-48)",
                    "minimum": 1,
                    "maximum": 48
                }
            },
            "required": ["page_number"]
        }
    },
    {
        "name": "get_duty_cycle",
        "description": "Look up the exact duty cycle for a specific welding process, input voltage, and optionally amperage. Returns duty cycle percentage, weld time, and cool-down time per 10-minute cycle. Source: page 29 of owner's manual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["MIG", "Flux-Core", "TIG", "Stick"],
                    "description": "Welding process"
                },
                "voltage": {
                    "type": "string",
                    "enum": ["120V", "240V"],
                    "description": "Input voltage"
                },
                "amperage": {
                    "type": "integer",
                    "description": "Optional: specific amperage to look up"
                }
            },
            "required": ["process", "voltage"]
        }
    },
    {
        "name": "get_troubleshooting",
        "description": "Look up troubleshooting entries for a specific problem or symptom. Returns matching problems with possible causes and solutions from the troubleshooting tables (pages 42-44).",
        "input_schema": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "description": "The problem or symptom (e.g., 'porosity', 'wire stops', 'arc not stable', 'welder won't turn on')"
                }
            },
            "required": ["symptom"]
        }
    },
    {
        "name": "get_polarity",
        "description": "Get the correct polarity setup (DCEP/DCEN) and cable socket configuration for a specific welding process. Shows which cable goes in which socket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["MIG", "Flux-Core", "TIG", "Stick"],
                    "description": "Welding process"
                }
            },
            "required": ["process"]
        }
    },
    {
        "name": "get_specifications",
        "description": "Get technical specifications for the welder including current ranges, duty cycles, wire capacities, and weldable materials. Can filter by process or return all.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["MIG", "TIG", "Stick"],
                    "description": "Optional: filter to a specific process"
                }
            }
        }
    },
    {
        "name": "get_selection_chart",
        "description": "Get the welding process selection chart — helps determine which process (MIG, Flux-Core, TIG, Stick) is best for a given material, thickness, skill level, and application.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "render_artifact",
        "description": """Generate an interactive HTML/SVG/CSS artifact that will be rendered visually in the user's browser. Use this for diagrams, calculators, flowcharts, tables, and any response better shown visually than described in text.

The HTML must be completely self-contained with inline CSS and JS. No external dependencies, CDNs, or imports. Use modern CSS (flexbox, grid) and vanilla JS only.

Examples of when to use:
- Polarity diagrams showing cable socket connections
- Duty cycle comparison tables with highlighting
- Troubleshooting decision flowcharts
- Settings calculators (process + material + thickness → recommended settings)
- Step-by-step setup guides with visual indicators""",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title shown in the artifact tab"
                },
                "html_content": {
                    "type": "string",
                    "description": "Complete self-contained HTML document with inline CSS and JS. Must work in a sandboxed iframe."
                },
                "artifact_type": {
                    "type": "string",
                    "enum": ["diagram", "calculator", "flowchart", "table", "schematic", "guide"],
                    "description": "Type of artifact for categorization"
                }
            },
            "required": ["title", "html_content", "artifact_type"]
        }
    }
]


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if tool_name == "search_manual":
        result = search_manual(tool_input["query"], tool_input.get("process_filter"))
    elif tool_name == "get_manual_page":
        result = get_manual_page(tool_input["page_number"])
    elif tool_name == "get_duty_cycle":
        result = get_duty_cycle(
            tool_input["process"],
            tool_input["voltage"],
            tool_input.get("amperage"),
        )
    elif tool_name == "get_troubleshooting":
        result = get_troubleshooting(tool_input["symptom"])
    elif tool_name == "get_polarity":
        result = get_polarity(tool_input["process"])
    elif tool_name == "get_specifications":
        result = get_specifications(tool_input.get("process"))
    elif tool_name == "get_selection_chart":
        result = get_selection_chart()
    elif tool_name == "render_artifact":
        # Artifact rendering is handled specially — we pass it through
        result = {
            "artifact_id": f"artifact_{hash(tool_input['title']) % 10000}",
            "title": tool_input["title"],
            "html_content": tool_input["html_content"],
            "artifact_type": tool_input["artifact_type"],
            "status": "rendered"
        }
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, ensure_ascii=False)


class VulcanAgent:
    """Manages conversation state and Claude API interactions."""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.conversations: dict[str, list] = {}

    def _get_messages(self, session_id: str) -> list:
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        return self.conversations[session_id]

    def chat(self, session_id: str, user_message: str, images: list[dict] | None = None):
        """
        Process a chat message and yield response chunks.
        Yields dicts with type: 'text', 'artifact', 'tool_use', 'done'
        """
        messages = self._get_messages(session_id)

        # Build user content
        content = []
        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/jpeg"),
                        "data": img["data"],
                    }
                })
        content.append({"type": "text", "text": user_message})

        messages.append({"role": "user", "content": content})

        # Agent loop: call Claude, process tool calls, repeat
        max_iterations = 10
        for _ in range(max_iterations):
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Process response content
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use
            tool_uses = [block for block in assistant_content if block.type == "tool_use"]

            if not tool_uses:
                # No tool calls — extract text and artifacts from response
                for block in assistant_content:
                    if block.type == "text":
                        yield {"type": "text", "content": block.text}
                yield {"type": "done"}
                return

            # Process tool calls
            tool_results = []
            for tool_use in tool_uses:
                yield {"type": "tool_use", "tool": tool_use.name, "input": tool_use.input}

                result_str = process_tool_call(tool_use.name, tool_use.input)

                # If it's an artifact, also yield it to the frontend
                if tool_use.name == "render_artifact":
                    result_data = json.loads(result_str)
                    yield {
                        "type": "artifact",
                        "title": result_data["title"],
                        "html_content": result_data["html_content"],
                        "artifact_type": result_data["artifact_type"],
                    }

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

        # If we hit max iterations
        yield {"type": "text", "content": "I've done extensive research but couldn't fully resolve your question. Could you rephrase or provide more details?"}
        yield {"type": "done"}

    def clear_session(self, session_id: str):
        """Clear conversation history for a session."""
        if session_id in self.conversations:
            del self.conversations[session_id]
