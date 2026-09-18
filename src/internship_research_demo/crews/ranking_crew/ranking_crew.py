from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from internship_research_demo.routing import make_report_url_guardrail


@CrewBase
class RankingCrew:
    """Crew that ranks verified internship candidates into a markdown report."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, allowed_urls: set[str] | None = None) -> None:
        self.allowed_urls = set(allowed_urls or ())

    @agent
    def ranking_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["ranking_analyst"],  # type: ignore[index]
            max_iter=8,
            verbose=True,
        )

    @task
    def ranking_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["ranking_report_task"],  # type: ignore[index]
            markdown=True,
            guardrail=make_report_url_guardrail(self.allowed_urls),
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
