import os
from mesa.datacollection import DataCollector
from mesa.model import Model
from mesa.space import MultiGrid, PropertyLayer
from rich import print

# Adjust these imports if your folder structure is different
from examples.saboteur.agents import (
    Impostor, Crewmate, 
    IMPOSTOR_SYSTEM_PROMPT, CREWMATE_SYSTEM_PROMPT
) 
from mesa_llm.reasoning.react import ReactReasoning # Import specific reasoning class

class GameModel(Model):
    def __init__(
        self,
        initial_imps: int = 1,
        initial_cms: int = 5,
        width: int = 10,
        height: int = 10,
        reasoning: type[ReactReasoning] = ReactReasoning, # Default to React
        llm_model: str = "llama3.1", # Default to a local model name
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
        
        # 2. Setup Task Layer (The "PropertyLayer")
        self.task_layer = PropertyLayer(
            name="task_locations", 
            width=self.width, 
            height=self.height, 
            default_value=0, 
            dtype=int
        )
        
        # 3. Place Random Tasks (set value to 1)
        task_x = self.rng.integers(0, self.grid.width, size=n_tasks)
        task_y = self.rng.integers(0, self.grid.height, size=n_tasks)
        
        for x, y in zip(task_x, task_y):
            self.task_layer.set_cell((x, y), 1)

        # 4. Data Collection
        model_reporters = {
            "Crewmates": lambda m: len([a for a in m.agents if isinstance(a, Crewmate) and a.state != "dead"]),
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
            system_prompt=Impostor.IMPOSTOR_SYSTEM_PROMPT if hasattr(Impostor, 'IMPOSTOR_SYSTEM_PROMPT') else IMPOSTOR_SYSTEM_PROMPT,
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
            system_prompt=Crewmate.CREWMATE_SYSTEM_PROMPT if hasattr(Crewmate, 'CREWMATE_SYSTEM_PROMPT') else CREWMATE_SYSTEM_PROMPT,
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
        
        # Advance Agents
        self.agents.shuffle_do("step")

        # Collect Data
        self.datacollector.collect(self)
        
        # Check Win Conditions
        self.check_game_over()

    def check_game_over(self):
        # Count active agents
        active_crewmates = [a for a in self.agents if isinstance(a, Crewmate) and a.state != "dead"]
        active_impostors = [a for a in self.agents if isinstance(a, Impostor)]

        # Condition 1: Impostor Win
        if len(active_crewmates) == 0:
            self.running = False
            print("\n[bold red]GAME OVER: IMPOSTORS WIN! (All Crewmates eliminated)[/bold red]")

        # Condition 2: Crewmate Win (Time Limit)
        elif self.steps >= self.max_steps:
            self.running = False
            print(f"\n[bold green]GAME OVER: CREWMATES WIN! (Survived {self.max_steps} steps)[/bold green]")
            
            
# ===============================================================
#                    RUN WITHOUT GRAPHICS (Test Llama 3.1)
# ===============================================================

if __name__ == "__main__":
    """
    Run this file directly to test the model with local Ollama Llama 3.1
    Command: python -m examples.saboteur.model
    """
    
    # 1. SETUP OLLAMA ENV (Overrides for local testing)
    # This tricks the library into talking to localhost:11434
    print("[bold blue]Configuring for Local Ollama...[/bold blue]")
    os.environ["OPENAI_API_KEY"] = "ollama"
    os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
    
    # 2. CONFIGURATION
    MODEL_NAME = "llama3.1" # Ensure you did 'ollama pull llama3.1'
    STEPS_TO_RUN = 10
    
    # 3. INITIALIZE
    print(f"Initializing GameModel with {MODEL_NAME}...")
    model = GameModel(
        initial_imps=1,
        initial_cms=3,   # Small number for faster local inference
        width=10, 
        height=10,
        llm_model=MODEL_NAME,
        max_steps=STEPS_TO_RUN
    )

    # 4. RUN LOOP
    try:
        while model.running and model.steps < STEPS_TO_RUN:
            model.step()
            
    except KeyboardInterrupt:
        print("[yellow]Stopping simulation...[/yellow]")
        