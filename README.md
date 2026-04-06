# Vulcan OmniPro 220 — Multimodal Reasoning Agent

<img src="product.webp" alt="Vulcan OmniPro 220" width="400" /> <img src="product-inside.webp" alt="Vulcan OmniPro 220 — inside panel" width="400" />

## The Problem

The Vulcan OmniPro 220 ships with a 48-page owner's manual covering four welding processes, dual voltage configurations, duty cycle matrices, polarity setups, wire feed mechanisms, troubleshooting tables, and wiring schematics. Nobody reads all 48 pages — but everyone needs the information at the exact moment they're standing in their garage with a welder they don't fully understand.

The gap isn't "information doesn't exist." It's "information isn't accessible in the moment it matters."

Having worked at SolidWorks, I've seen this pattern repeatedly: engineers and makers have access to extensive technical documentation, but the way they actually need information delivered — contextual, visual, and in the language of their current task — is fundamentally different from how manuals present it. A 48-page PDF organized by chapter is optimized for printing, not for the person who just heard a strange noise from their wire feed mechanism.

## Quick Start

```bash
git clone <this-repo>
cd <this-repo>
cp .env.example .env          # Add your ANTHROPIC_API_KEY
pip install -r requirements.txt
cd frontend && npm install && cd ..
python run.py                 # Opens at http://localhost:5173
```

## How It Works

### Architecture

```
React Frontend (Vite + Tailwind)
    ↕ SSE streaming
FastAPI Backend (Python)
    ↕ Anthropic API with tool use
Claude Agent (Sonnet 4 + 7 custom tools + knowledge base)
```

### Knowledge Extraction

The three source documents (48-page owner's manual, 2-page quick start guide, 1-page selection chart) are pre-processed into a structured knowledge base:

1. **Every page** is converted to a PNG image at 300 DPI using PyMuPDF
2. **Text content** is extracted and organized into 22 sections, each tagged with applicable welding processes (MIG, Flux-Core, TIG, Stick)
3. **Critical tables** (duty cycles, specifications, troubleshooting, polarity configurations) are extracted as structured JSON with verified values
4. **A keyword index** maps 53 search terms to relevant sections and page numbers

The knowledge base ships pre-built in the repo — no extraction step needed to run.

### The Agent

The agent uses Claude Sonnet 4 with 7 custom tools:

| Tool | Purpose |
|------|---------|
| `search_manual` | Keyword/topic search across all manual sections, with optional process filtering |
| `get_manual_page` | Retrieve full content and image URL for a specific page |
| `get_duty_cycle` | Exact duty cycle lookup by process, voltage, and amperage |
| `get_troubleshooting` | Problem/symptom lookup against the troubleshooting tables |
| `get_polarity` | Cable socket configuration for each welding process |
| `get_specifications` | Technical specs (current ranges, wire capacities, materials) |
| `render_artifact` | Generate interactive HTML/SVG artifacts rendered in the browser |

**Key design decisions:**

- **Polarity facts are hardcoded in the system prompt**, not left to retrieval. Getting polarity wrong (DCEP vs DCEN) can damage the machine or injure the user. This is too safety-critical to leave to search relevance scoring.
- **Section-level retrieval**, not full-context stuffing. Each query searches the index and returns 1-5 relevant sections (~3000 chars each), keeping context lean and responses fast.
- **Process-aware filtering.** When the user has established they're doing TIG welding, searches are scoped to TIG-relevant sections first, preventing cross-process contamination (MIG and Flux-Core have opposite polarity — returning the wrong one is dangerous).
- **Multi-step reasoning.** Complex questions trigger multiple tool calls before the agent answers. "Porosity at 180A" searches troubleshooting AND checks duty cycle AND reviews settings.

### Visual Responses (Artifacts)

The agent generates self-contained HTML/SVG artifacts rendered in a sandboxed iframe panel — modeled after Claude.ai's artifact system. The agent decides when to use visuals based on the question type:

- **Polarity/wiring questions** → SVG diagram of the front panel with cable routing
- **Duty cycle questions** → Interactive table with highlighted values
- **Troubleshooting** → Diagnostic flowcharts
- **Setup procedures** → Step-by-step visual guides
- **Simple factual questions** → Text-only (no unnecessary artifacts)

### Conversation State

The agent tracks user context across the conversation: input voltage, welding process, wire type, material, thickness. If you say "I'm on 120V" and later ask "what's my max amperage?", it remembers the voltage.

## Knowledge as a Graph

The manual's content forms an implicit knowledge graph:

```
Welding Process (MIG/TIG/Stick/Flux-Core)
    → requires Polarity (DCEP/DCEN)
        → determines Socket Configuration (which cable → which socket)
    → has Duty Cycle (varies by voltage and amperage)
        → limits Work Duration (X min welding, Y min cooling)
    → requires Settings (wire speed, voltage, gas flow)
        → varies by Material + Thickness
    → can produce Defects (porosity, undercut, spatter)
        → diagnosed via Troubleshooting Table
            → has Causes + Solutions
```

This is what Prox is building at scale — not just for one welder, but for every complex product. The structured knowledge extraction approach here is product-agnostic: drop a new manual in `files/`, run `extract.py`, and the agent serves a new product.

## What I'd Build Next

- **Voice input** — the user is in a garage with dirty hands, typing is friction
- **Photo diagnosis** — upload a photo of a bad weld, get visual comparison with the manual's reference images
- **Settings configurator** — select process + material + thickness → get recommended wire speed, voltage, gas flow as an interactive widget
- **Session persistence** — save and resume conversations across visits
- **Multi-product support** — serve multiple product manuals from a single agent

## Project Structure

```
├── files/                    # Source PDFs (owner's manual, quick start, selection chart)
├── knowledge/                # Pre-extracted knowledge base (shipped in repo)
│   ├── extract.py           # Extraction script (optional — pre-built data included)
│   ├── pages/               # PNG of every manual page at 300 DPI
│   ├── sections.json        # 22 sections with text content and process tags
│   ├── tables.json          # Structured data: duty cycles, specs, troubleshooting, polarity
│   └── index.json           # 53-term keyword → section/page search index
├── backend/
│   ├── main.py              # FastAPI server with SSE streaming
│   ├── agent.py             # Claude agent with system prompt and 7 tools
│   └── knowledge.py         # Knowledge base query functions
├── frontend/
│   └── src/
│       ├── App.tsx          # Chat UI + artifact panel + image upload + onboarding
│       └── types.ts         # TypeScript interfaces
├── run.py                   # Single entry point — starts backend + frontend
├── requirements.txt
└── .env.example             # Only needs ANTHROPIC_API_KEY
```

## Tech Stack

- **Backend:** Python, FastAPI, Anthropic SDK
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Agent:** Claude Sonnet 4 with tool use
- **Knowledge extraction:** PyMuPDF for PDF → PNG, structured JSON for tables/indices
