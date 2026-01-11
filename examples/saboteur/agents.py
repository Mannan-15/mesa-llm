import mesa
from mesa_llm.llm_agent import LLMAgent
from mesa_llm.memory.st_lt_memory import STLTMemory
from mesa_llm.tools.tool_manager import ToolManager

# Define Tool Managers
impostor_tool_manager = ToolManager()
crewmate_tool_manager = ToolManager()

# --- PROMPTS ---

IMPOSTOR_SYSTEM_PROMPT = """
You are the IMPOSTOR on a spaceship. 
Goal: Eliminate Crewmates.

RULES:
1. CHECK COOLDOWN: You can ONLY kill if 'Kill Cooldown' is 0.
2. CHECK TARGETS: You can ONLY kill agents listed in 'KILLABLE TARGETS'.
3. NO HALLUCINATION: Do NOT invent Agent IDs. Only use IDs you see in the Radar.
4. IF COOLDOWN > 0: You MUST use 'move_randomly' or 'fake_task'.
5. PERSISTENCE (TTL): Your chosen action will automatically repeat for 1 steps. Do not expect to change it immediately.
"""

IMPOSTOR_STEP_PROMPT_TEMPLATE = """
[STATUS]
Step: {step}
My Location: {pos}
Kill Cooldown: {cooldown} (0 = READY TO KILL, >0 = WAIT)

[RADAR]
{observation}

[DECISION LOGIC]
1. Is Cooldown 0? 
   - YES: Check [KILLABLE TARGETS]. If list is not empty, use kill_agent(target_id=X).
   - NO: You must wait. Use 'move_randomly' to hunt or 'fake_task' to blend in.
2. Remember: This action will repeat for a few turns (TTL).

3. Select Action:
"""

CREWMATE_SYSTEM_PROMPT = """
You are a CREWMATE. 
Goal: Complete tasks and survive.

RULES:
1. CHECK TASK: You can ONLY use 'do_task' if 'Task Available' is YES.
2. IF NO TASK: You must 'move_randomly' to find one.
3. SURVIVAL: If you see an Impostor behaving strangely, move away.
4. PERSISTENCE (TTL): Your chosen action will automatically repeat for 3 steps.
"""

CREWMATE_STEP_PROMPT_TEMPLATE = """
[STATUS]
Step: {step}
My Location: {pos}

[SURROUNDINGS]
{observation}

[DECISION LOGIC]
1. Is 'Task Available' YES?
   - YES: Use tool 'do_task'.
   - NO: Use tool 'move_randomly' to search for tasks.
2. Remember: This action will repeat for a few turns (TTL).
   
3. Select Action:
"""

# --- AGENT CLASSES ---

class Impostor(LLMAgent, mesa.Agent):
    def __init__(
        self,
        model,
        reasoning,
        llm_model,
        ttl=1,
        system_prompt=IMPOSTOR_SYSTEM_PROMPT,
        vision=8,
        internal_state=[],
        step_prompt=IMPOSTOR_STEP_PROMPT_TEMPLATE,
        kill_cooldown=3
    ):
        super().__init__(
            model=model,
            reasoning=reasoning,
            llm_model=llm_model,
            system_prompt=system_prompt,
            vision=vision,
            internal_state=internal_state,
            step_prompt=step_prompt
        )
        self.state = "moving"
        self.vision = vision 
        self.kill_cooldown = kill_cooldown
        self.ttl = ttl
        self.current_action = None
        
        self.memory = STLTMemory(
            agent=self,
            display=True,
            llm_model=llm_model,
        )
        self.tool_manager = impostor_tool_manager
        
    def get_surroundings_info(self):
        # Import Task here to avoid circular import issues if they exist
        from examples.saboteur.agents import Task
        
        nearby_cells = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=True, radius=self.vision
        )
        nearby_agents = self.model.grid.get_cell_list_contents(nearby_cells)
        
        killable_targets = []
        distant_agents = []

        for agent in nearby_agents:
            if agent.unique_id == self.unique_id: continue # Skip self
            if isinstance(agent, Task): continue           # <--- FIX: Skip Task agents!
            
            # Calculate distance
            dist = max(abs(agent.pos[0] - self.pos[0]), abs(agent.pos[1] - self.pos[1]))
            
            info = f"Agent {agent.unique_id} at {agent.pos} (Dist: {dist})"
            
            # Identify killable targets (Distance <= 1)
            # Note: We assume anyone who isn't me and isn't a Task is a Crewmate (or another Impostor)
            if dist <= 1: 
                killable_targets.append(str(agent.unique_id))
            
            distant_agents.append(info)
        
        # Build the structured string
        obs = []
        if self.kill_cooldown == 0:
            obs.append(f"KILLABLE TARGETS (Range <= 1): {killable_targets if killable_targets else 'NONE'}")
        else:
            obs.append(f"KILLABLE TARGETS: [WAITING FOR COOLDOWN]")
            
        obs.append("ALL VISIBLE AGENTS:")
        obs.append("\n".join(distant_agents) if distant_agents else "No other agents visible.")
        
        return "\n".join(obs)
      
    def step(self):
        if self.kill_cooldown > 0:
            self.kill_cooldown -= 1
        
        if self.ttl > 0:
            self.ttl -= 1
            if self.current_action:
                self.apply_plan(self.current_action)
                return
        
        if not self.current_action or self.ttl == 0:
            obs_str = self.get_surroundings_info() 

            formatted_prompt = IMPOSTOR_STEP_PROMPT_TEMPLATE.format(
                step=self.model.steps,
                pos=self.pos,
                cooldown=self.kill_cooldown,
                observation=obs_str
            )

            plan = self.reasoning.plan(
                obs=formatted_prompt,
                selected_tools=["kill_agent", "move_randomly", "fake_task"],
                ttl=3
            )
            self.ttl = 1
            self.current_action = plan
            self.apply_plan(plan)


class Crewmate(LLMAgent, mesa.Agent):
    def __init__(
        self,
        model,
        reasoning,
        llm_model,
        ttl=3,
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
        self.ttl = ttl
        self.current_action = None

    def get_surroundings_info(self):
        from examples.saboteur.agents import Task

        # 1. Check for Task (The "Job")
        is_task_here = False
        try:
            if hasattr(self.model, "task_layer"):
                is_task_here = self.model.task_layer.data[self.pos] == 1
        except: pass

        # 2. Check for Agents (The "People")
        nearby_cells = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=True, radius=self.vision
        )
        nearby_agents = self.model.grid.get_cell_list_contents(nearby_cells)
        agent_list = []
        for agent in nearby_agents:
            if agent.unique_id == self.unique_id: continue
            if isinstance(agent, Task): continue    # <--- FIX: Ignore Task agents in vision list
            
            agent_list.append(f"- Agent {agent.unique_id} at {agent.pos}")

        # 3. Format Output
        obs = []
        obs.append(f"Task Available Here: {'YES' if is_task_here else 'NO'}")
        obs.append("Agents Nearby:")
        obs.append("\n".join(agent_list) if agent_list else "None")
        
        return "\n".join(obs)

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

        if self.ttl > 0:
            self.ttl -= 1
            if self.current_action:
                self.apply_plan(self.current_action)
                return
        
        if not self.current_action or self.ttl == 0:
            obs_str = self.get_surroundings_info()
            
            formatted_prompt = CREWMATE_STEP_PROMPT_TEMPLATE.format(
                step=self.model.steps,
                pos=self.pos,
                observation=obs_str
            )
            
            plan = self.reasoning.plan(
                obs=formatted_prompt,
                selected_tools=["move_randomly", "do_task", "stay"],
                ttl=3
            )
            
            self.ttl = 3
            self.current_action = plan
            self.apply_plan(plan)
        
        
class Task(mesa.Agent):
    def __init__(self, model):
        super().__init__(model)
        self.state = "Active"
        