from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool


@CrewBase
class InternshipResearchCrew:
    """Crew that researches and ranks internship opportunities."""

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

    @agent
    def ranking_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["ranking_analyst"],  # type: ignore[index]
            max_iter=8,
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
        )

    @task
    def ranking_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["ranking_report_task"],  # type: ignore[index]
            markdown=True,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the internship research crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
