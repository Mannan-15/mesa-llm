import os
import mesa
from mesa.datacollection import DataCollector
from mesa.model import Model
from mesa.space import MultiGrid, PropertyLayer
# NOTE: No "from mesa.time import ..." needed in Mesa 3.0!
from rich import print

# Adjust imports if needed
from examples.saboteur.agents import (
    Impostor, Crewmate, 
    IMPOSTOR_SYSTEM_PROMPT, CREWMATE_SYSTEM_PROMPT
) 
from mesa_llm.reasoning.react import ReActReasoning 

class GameModel(Model):
    def __init__(
        self,
        initial_imps: int = 1,
        initial_cms: int = 5,
        width: int = 10,
        height: int = 10,
        reasoning: type[ReActReasoning] = ReActReasoning, 
        llm_model: str = "llama3.1", 
        vision: int = 8,
        max_steps: int = 30,
        n_tasks: int = 10,
        seed=None
    ):
        
        super().__init__(seed=seed)
        
        self.width = width
        self.height = height
        self.max_steps = max_steps
        self.running = True
        
        # 1. Setup Grid
        self.grid = MultiGrid(self.width, self.height, torus=False)
        
        # 2. Setup Task Layer
        self.task_layer = PropertyLayer(
            name="task_locations", 
            width=self.width, 
            height=self.height, 
            default_value=0, 
            dtype=int
        )
        
        # Place Random Tasks
        task_x = self.rng.integers(0, self.grid.width, size=n_tasks)
        task_y = self.rng.integers(0, self.grid.height, size=n_tasks)
        
        for x, y in zip(task_x, task_y):
            self.task_layer.set_cell((x, y), 1)

        # 3. Data Collection
        # In Mesa 3.0, we check 'model.agents' instead of 'schedule.agents'
        model_reporters = {
            "Crewmates": lambda m: len([a for a in m.agents if isinstance(a, Crewmate) and a.state != "dead"]),
            "Impostors": lambda m: len([a for a in m.agents if isinstance(a, Impostor)])
        }
        agent_reporters = {}
        
        self.datacollector = DataCollector(
            model_reporters=model_reporters, agent_reporters=agent_reporters
        )
        
        # --- IMPOSTOR CREATION ---
        for i in range(initial_imps):
            impostor = Impostor(
                model=self,
                reasoning=reasoning,
                llm_model=llm_model,
                system_prompt=IMPOSTOR_SYSTEM_PROMPT,
                vision=vision,
                step_prompt="Look for crewmates to eliminate."
            )
            # Mesa 3.0 automatically adds 'impostor' to self.agents when initialized with 'model=self'
            x = self.rng.integers(0, self.grid.width)
            y = self.rng.integers(0, self.grid.height)
            self.grid.place_agent(impostor, (x, y))

        # --- CREWMATE CREATION ---
        for i in range(initial_cms):
            crewmate = Crewmate(
                model=self,
                reasoning=reasoning,
                llm_model=llm_model,
                system_prompt=CREWMATE_SYSTEM_PROMPT,
                vision=vision,
                step_prompt="Focus on survival and tasks."
            )
            x = self.rng.integers(0, self.grid.width)
            y = self.rng.integers(0, self.grid.height)
            self.grid.place_agent(crewmate, (x, y))
            
    def step(self):
        """
        Execute one step of the model.
        """
        print(
            f"\n[bold purple] Step {self.steps} ────────────────────────────────────────────────────────────────────────────────[/bold purple]"
        )
        
        # Mesa 3.0: Use the built-in agent set
        self.agents.shuffle_do("step")

        # Collect Data
        self.datacollector.collect(self)
        
        # Check Win Conditions
        self.check_game_over()

    def check_game_over(self):
        active_crewmates = [a for a in self.agents if isinstance(a, Crewmate) and a.state != "dead"]
        
        if len(active_crewmates) == 0:
            self.running = False
            print("\n[bold red]GAME OVER: IMPOSTORS WIN! (All Crewmates eliminated)[/bold red]")

        elif self.steps >= self.max_steps:
            self.running = False
            print(f"\n[bold green]GAME OVER: CREWMATES WIN! (Survived {self.max_steps} steps)[/bold green]")
            