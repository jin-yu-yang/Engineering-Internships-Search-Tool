from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

from internship_research_demo.models import ResearchBrief
from internship_research_demo.routing import research_guardrail


@CrewBase
class ResearchCrew:
    """Crew that researches internship candidates from one source focus."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def internship_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["internship_researcher"],  # type: ignore[index]
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
            max_iter=12,
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
            output_pydantic=ResearchBrief,
            guardrail=research_guardrail,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
