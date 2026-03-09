import os
import mesa
from mesa.datacollection import DataCollector
from mesa.model import Model
from mesa.space import MultiGrid, PropertyLayer
from rich import print

# Adjust imports if needed
from examples.saboteur.agents import (
    Impostor, Crewmate, Task,
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
        llm_model: str = "gpt-4o-mini",  # <--- CHANGED DEFAULT
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
        self.phase = "active"
        self.discussion_trigger_data = {"report_id": None}
        
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
            
            # Place Visual Task Agents
            cell_contents = self.grid.get_cell_list_contents([(x, y)])
            # Avoid placing duplicate tasks
            if not any(isinstance(obj, Task) for obj in cell_contents):
                task_agent = Task(self)
                self.grid.place_agent(task_agent, (x, y))

        # 3. Data Collection
        model_reporters = {
            "Crewmates": lambda m: len([a for a in m.agents if isinstance(a, Crewmate) and a.state != "dead"]),
            "Impostors": lambda m: len([a for a in m.agents if isinstance(a, Impostor)])
        }
        agent_reporters = {}
        
        self.datacollector = DataCollector(
            model_reporters=model_reporters, agent_reporters=agent_reporters
        )
        
        # --- IMPOSTOR CREATION ---
        impostors = []
        for i in range(initial_imps):
            impostor = Impostor(
                model=self,
                reasoning=reasoning,
                llm_model=llm_model,
                system_prompt=IMPOSTOR_SYSTEM_PROMPT,
                vision=vision,
                step_prompt="Look for crewmates to eliminate."
            )
            
            x = self.rng.integers(0, self.grid.width)
            y = self.rng.integers(0, self.grid.height)
            impostors.append(impostor)
            self.grid.place_agent(impostor, (x, y))

        impostor_ids = [imp.unique_id for imp in impostors]
        for imp in impostors:
            imp.team_ids = impostor_ids
            
        # NEW PARAMETER (GSoC Upgrade)
        backstories_cm = ["You are a paranoid veteran astronaut. You have survived an Impostor attack before.\
                You trust absolutely no one. If another agent gets too close to you, your first priority is to run away.\
                You prioritize your own survival over completing tasks.",
                "You are the ship's unofficial detective. You are highly observant. Instead of just doing tasks,\
                you like to follow other agents from a safe distance to see if they are doing tasks or just wandering around suspiciously.\
                You are eager to report dead bodies and find the killer.",]
            
        # --- CREWMATE CREATION ---
        for i in range(initial_cms):
            crewmate = Crewmate(
                model=self,
                reasoning=reasoning,
                llm_model=llm_model,
                system_prompt=CREWMATE_SYSTEM_PROMPT,
                vision=vision,
                step_prompt="Focus on survival and tasks.",
                backstory=backstories_cm[i%2],
            )
            x = self.rng.integers(0, self.grid.width)
            y = self.rng.integers(0, self.grid.height)
            self.grid.place_agent(crewmate, (x, y))
            
    def step(self):
        """Execute one step of the model."""
        print(
            f"\n[bold purple] Step {self.steps} ────────────────────────────────────────────────────────────────────────────────[/bold purple]"
        )
        if hasattr(self, "phase") and self.phase == "active":
            self.agents.shuffle_do("step")
            self.datacollector.collect(self)
            self.check_game_over()
            
        elif self.phase == "discussion":
            self.run_discussion_logic()
            self.phase = "active"
            self.check_game_over()
            

    def check_game_over(self):
        active_crewmates = [a for a in self.agents if isinstance(a, Crewmate) and a.state != "dead"]
        
        if len(active_crewmates) == 0:
            self.running = False
            print("\n[bold red]GAME OVER: IMPOSTORS WIN! (All Crewmates eliminated)[/bold red]")

        elif self.steps >= self.max_steps:
            self.running = False
            print(f"\n[bold green]GAME OVER: CREWMATES WIN! (Survived {self.max_steps} steps)[/bold green]")
            
    def run_discussion_logic(self):
        print(f"\n--- DISCUSSION STARTED BY AGENT {self.discussion_trigger_data['report_id']} ---")
        
        # GATHER & FREEZE
        prev_pos = {}
        for agent in self.agents:
            if isinstance(agent, Task):
                continue
            if (isinstance(agent, Crewmate) and hasattr(agent, "state") and agent.state == "dead"):
                self.grid.remove_agent(agent)
            prev_pos[agent.unique_id] = agent.pos
            self.grid.place_agent(agent, (self.width // 2, self.height // 2))
            
        # COLLECT VOTES
        votes = {}
        
            
        
    def trigger_meeting(self):
        pass
            