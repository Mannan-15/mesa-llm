from mesa.datacollection import DataCollector
from mesa.model import Model
from mesa.space import MultiGrid
from rich import print

from examples.saboteur.agents import (
    Impostor, Crewmate, 
    IMPOSTOR_SYSTEM_PROMPT, CREWMATE_SYSTEM_PROMPT
) 

from mesa_llm.reasoning.reasoning import Reasoning

class GameModel(Model):
    def __init__(
        self,
        initial_imps: int = 1,
        initial_cms: int = 5,
        width: int = 10,
        height: int = 10,
        reasoning: type[Reasoning] = None,
        llm_model: str = "",
        vision: int = 8,
        max_steps: int = 30,
        seed=None
    ):
        
        super().__init__(seed=seed)
        
        self.width = width
        self.height = height
        self.max_steps = max_steps
        self.running = True
        
        self.grid = MultiGrid(self.width, self.height, torus=False)

        model_reporters = {
            "Crewmates": lambda m: len([a for a in m.agents if isinstance(a, Crewmate)]),
            "Impostors": lambda m: len([a for a in m.agents if isinstance(a, Impostor)])
        }
        agent_reporters = {}
        
        self.datacollector = DataCollector(
            model_reporters=model_reporters, agent_reporters=agent_reporters
        )
        
        # --- IMPOSTOR CREATION ---
        impostor_agents = Impostor.create_agents(
            self,
            n=initial_imps,
            reasoning=reasoning,
            llm_model=llm_model,
            system_prompt=Impostor.IMPOSTOR_SYSTEM_PROMPT if hasattr(Impostor, 'IMPOSTOR_SYSTEM_PROMPT') else "You are an Impostor.",
            vision=vision,
            internal_state=None,
            step_prompt="Look for crewmates to eliminate.", 
        )

        # Place Impostors
        x = self.rng.integers(0, self.grid.width, size=(initial_imps))
        y = self.rng.integers(0, self.grid.height, size=(initial_imps))
        for a, i, j in zip(impostor_agents, x, y):
            self.grid.place_agent(a, (i, j))

        # --- CREWMATE CREATION ---
        crewmate_agents = Crewmate.create_agents(
            self,
            n=initial_cms,
            reasoning=reasoning,
            llm_model=llm_model,
            system_prompt=Crewmate.CREWMATE_SYSTEM_PROMPT if hasattr(Crewmate, 'CREWMATE_SYSTEM_PROMPT') else "You are a Crewmate.",
            vision=vision,
            internal_state=None,
            step_prompt="Focus on survival and tasks.",
        )

        # Place Crewmates
        x = self.rng.integers(0, self.grid.width, size=(initial_cms))
        y = self.rng.integers(0, self.grid.height, size=(initial_cms))
        for a, i, j in zip(crewmate_agents, x, y):
            self.grid.place_agent(a, (i, j))
            
    def step(self):
        """
        Execute one step of the model.
        """
        
        print(
            f"\n[bold purple] Step {self.steps} ────────────────────────────────────────────────────────────────────────────────[/bold purple]"
        )
        
        self.agents.shuffle_do("step")

        self.datacollector.collect(self)
        
        self.check_game_over()

    def check_game_over(self):
        # Count active agents on the grid
        # Note: This relies on the Kill Tool actually removing the agent from the model/grid
        active_crewmates = [a for a in self.agents if isinstance(a, Crewmate) and a.state != "dead"]
        active_impostors = [a for a in self.agents if isinstance(a, Impostor)]

        # Condition 1: Impostor Win (All Crewmates Dead)
        if len(active_crewmates) == 0:
            self.running = False
            print("\n[bold red]GAME OVER: IMPOSTORS WIN! (All Crewmates eliminated)[/bold red]")

        # Condition 2: Impostor Win (Equal Numbers - specific to Among Us rules, optional)
        # elif len(active_impostors) >= len(active_crewmates):
        #     self.running = False
        #     print("\n[bold red]GAME OVER: IMPOSTORS WIN! (Crewmates outnumbered)[/bold red]")

        # Condition 3: Crewmate Win (Time Limit Reached)
        elif self.steps >= self.max_steps:
            self.running = False
            print(f"\n[bold green]GAME OVER: CREWMATES WIN! (Survived {self.max_steps} steps)[/bold green]")
            
            
# ===============================================================
#                     RUN WITHOUT GRAPHICS
# ===============================================================

if __name__ == "__main__":
    """
    run the model without the solara integration with:
    conda activate mesa-llm && python -m examples.negotiation.model
    """

    from examples.saboteur.app import model

    # Run the model for 10 steps
    for _ in range(10):
        model.step()