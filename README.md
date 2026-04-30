# Internship Research Agent

A lightweight CrewAI Flow and CLI tool designed to automate the research, verification, and ranking of internship opportunities within specific applied science or engineering fields.

The final intelligence report is saved to:
`output/internship_report.md`

---

## 🚀 How It Works

The project orchestrates a sequential CrewAI Flow consisting of two specialized agents:

1.  **Internship Researcher**: Scours the web and verifies live internship listings using advanced search tools.
2.  **Ranking Analyst**: Evaluates findings based on user criteria and generates a structured, ranked Markdown report.

### Default Configuration
Key parameters are defined in `src/internship_research_demo/main.py`, including:
* **Field:** Software engineering and applied AI
* **Season:** Summer 2026
* **Location:** United States (supporting CPT/OPT requirements)
* **Count:** 3 opportunities by default

---

## 🛠️ Installation

### Prerequisites
* **Python:** >= 3.10, < 3.14
* **Package Manager:** [UV](https://docs.astral.sh/uv/) (Required for the CrewAI CLI)

### Setup
1.  **Install dependencies:**
    ```bash
    crewai install
    ```

2.  **Environment Variables:**
    Create a `.env` file and add your API keys:
    ```bash
    OPENAI_API_KEY=your_key_here
    SERPER_API_KEY=your_key_here
    ```
---

## 🖥️ Running the Agent

### Interactive Mode
The recommended way to use the agent is via the interactive CLI:
```bash
uv run internship-agent --interactive
```

### Direct CLI Flags
You can also bypass the prompts by passing arguments directly:
```bash
uv run internship-agent \
  --field "robotics engineering" \
  --season "Summer 2026" \
  --location "United States" \
  --work-mode remote \
  --work-mode hybrid \
  --require-opt-cpt \
  --count 5 \
  --output robotics_report.md
```

### Standard CrewAI Commands
If you prefer to run the flow using the standard CrewAI entry points:
* **Default run:** `crewai run`
* **Triggered run:** ```bash
    crewai run_with_trigger '{"applied_field":"biomedical engineering","work_modes":"remote, hybrid","opportunity_count":3}'
    ```

---

## 📂 Project Structure (Files to Edit)

| Component | Path |
| :--- | :--- |
| **Orchestration** | `src/internship_research_demo/main.py` |
| **CLI Logic** | `src/internship_research_demo/cli.py` |
| **Agent Config** | `src/.../config/agents.yaml` |
| **Task Config** | `src/.../config/tasks.yaml` |
| **Crew Wiring** | `src/.../content_crew.py` |

---

### Pro-Tip: Isolated Storage
To keep CrewAI storage files localized within this directory during experimentation:
```bash
HOME="$PWD" CREWAI_STORAGE_DIR=crewai_storage uv run internship-agent --interactive
```