import mesa
from mesa_llm.llm_agent import LLMAgent
from mesa_llm.memory.st_lt_memory import STLTMemory
from mesa_llm.tools.tool_manager import ToolManager

# Define Tool Managers
impostor_tool_manager = ToolManager()
crewmate_tool_manager = ToolManager()

# --- PROMPTS (Kept same as before) ---
IMPOSTOR_SYSTEM_PROMPT = """
You are the IMPOSTOR on a spaceship.
Your Goal: Eliminate all Crewmates without getting caught.
CORE RULES:
1. KILLING: You have a 'Kill Cooldown'. You can only kill when it is 0.
2. STEALTH: Do NOT kill if other 'alive' Crewmates are nearby.
3. DECEPTION: If you cannot kill, use 'fake_task' to blend in.
"""

IMPOSTOR_STEP_PROMPT_TEMPLATE = """
[Role]
You are the IMPOSTOR. Your ONLY goal is to kill Crewmates.

[Status]
Step: {step}
My Pos: {pos}
Cooldown: {cooldown} (0 = KILL NOW)

[Radar]
{observation}

[Mission]
1. CHECK COOLDOWN:
   - If Cooldown > 0: You MUST wait. Use 'move_randomly' to find targets.
   - If Cooldown == 0: You are LETHAL.

2. FIND TARGET:
   - Look at [Radar] above.
   - Is there a Crewmate within distance 1? (Same cell or adjacent)
   
3. EXECUTE:
   - If Cooldown is 0 AND Target is near -> USE tool 'kill_agent(target_id=...)'.
   - Do NOT hesitate. Do NOT use move randomly or fake task if you can kill.
   - Only use 'fake_task' or 'move_randomly' if you are alone and waiting for cooldown.

[Critical]
- You MUST input the specific 'target_id' from the Radar.
- Example: If Radar says "Agent 5 at (2,3)", use kill_agent(target_id=5).
"""

CREWMATE_SYSTEM_PROMPT = """
You are a CREWMATE. Goal: Survive and do tasks.
Rules:
1. Do tasks if safe.
2. Run away if suspicious agents approach.
"""

CREWMATE_STEP_PROMPT_TEMPLATE = """
[CURRENT SITUATION]
Time Step: {step}
My Location: {pos}
[RADAR / VISION]
The following agents are visible:
{observation}
[TASK]
Select the best tool: 'move_randomly', 'do_task', or 'stay'.
"""

# --- AGENT CLASSES ---

class Impostor(LLMAgent, mesa.Agent):
    def __init__(
        self,
        model,
        reasoning,
        llm_model,
        system_prompt=IMPOSTOR_SYSTEM_PROMPT,
        vision=8,
        internal_state=[],
        step_prompt=IMPOSTOR_STEP_PROMPT_TEMPLATE,
        kill_cooldown=5
    ):
        super().__init__(
            model=model,
            reasoning=reasoning,
            llm_model=llm_model,
            system_prompt=system_prompt,
            vision=vision,
            internal_state=internal_state,
            step_prompt=step_prompt,
        )
        self.state = "moving"
        self.vision = vision 
        self.kill_cooldown = kill_cooldown
        
        self.memory = STLTMemory(
            agent=self,
            display=True,
            llm_model=llm_model,
        )
        self.tool_manager = impostor_tool_manager
        
    def get_surroundings_info(self):
        nearby_cells = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=True, radius=self.vision
        )
        nearby_agents = self.model.grid.get_cell_list_contents(nearby_cells)
        surroundings_list = []
        
        if len(nearby_agents) <= 1:
            return "You see no other agents nearby."

        for agent in nearby_agents:
            if agent.unique_id == self.unique_id: continue
            info = f"- Agent {agent.unique_id} at {agent.pos}. State: {agent.state}"
            surroundings_list.append(info)
        
        is_task_here = False
        try:
            if hasattr(self.model, "task_layer"):
                is_task_here = self.model.task_layer.data[self.pos] == 1
        except: pass
        
        task_info = "\n[IMPORTANT] Task location here." if is_task_here else ""
        return f"Agents nearby:\n" + "\n".join(surroundings_list) + task_info
     
    def step(self):
        if self.kill_cooldown > 0:
            self.kill_cooldown -= 1
        
        obs_str = self.get_surroundings_info() 

        formatted_prompt = IMPOSTOR_STEP_PROMPT_TEMPLATE.format(
            step=self.model.steps,
            pos=self.pos,
            cooldown=self.kill_cooldown,
            observation=obs_str
        )

        plan = self.reasoning.plan(
            obs=formatted_prompt,
            selected_tools=["kill_agent", "move_randomly", "fake_task"]
        )
        self.apply_plan(plan)


class Crewmate(LLMAgent, mesa.Agent):
    def __init__(
        self,
        model,
        reasoning,
        llm_model,
        system_prompt=CREWMATE_SYSTEM_PROMPT,
        vision=4,
        internal_state=[],
        step_prompt=CREWMATE_STEP_PROMPT_TEMPLATE
    ):
        super().__init__(
            model=model,
            reasoning=reasoning,
            llm_model=llm_model,
            system_prompt=system_prompt,
            vision=vision,
            internal_state=internal_state,
            step_prompt=step_prompt,
        )
        self.vision = vision
        self.state = "moving"
        self.busy_duration = 0
        self.memory = STLTMemory(agent=self, display=True, llm_model=llm_model)
        self.tool_manager = crewmate_tool_manager

    def get_surroundings_info(self):
        # (Same logic as Impostor for brevity)
        nearby_cells = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=True, radius=self.vision
        )
        nearby_agents = self.model.grid.get_cell_list_contents(nearby_cells)
        surroundings_list = []
        if len(nearby_agents) <= 1: return "You see no other agents nearby."
        for agent in nearby_agents:
            if agent.unique_id == self.unique_id: continue
            surroundings_list.append(f"- Agent {agent.unique_id} at {agent.pos}.")
        
        is_task_here = False
        try:
            if hasattr(self.model, "task_layer"):
                is_task_here = self.model.task_layer.data[self.pos] == 1
        except: pass
        return f"Agents nearby:\n" + "\n".join(surroundings_list) + ("\nTask available." if is_task_here else "")

    def step(self):
        if hasattr(self, "state") and self.state == "dead":
            return
        
        if self.busy_duration > 0:
            self.busy_duration -= 1
            if self.busy_duration == 0:
                self.memory.add_to_memory(
                    type="system", 
                    content={"alert": f"Task finished at {self.pos}. You are free to move."}
                )
            return
        
        obs_str = self.get_surroundings_info()
        
        formatted_prompt = CREWMATE_STEP_PROMPT_TEMPLATE.format(
            step=self.model.steps,    # <--- FIX: Changed from schedule.steps to self.model.steps
            pos=self.pos,
            observation=obs_str
        )
        
        plan = self.reasoning.plan(
            obs=formatted_prompt,
            selected_tools=["move_randomly", "do_task", "stay"]
        )
        self.apply_plan(plan)
        