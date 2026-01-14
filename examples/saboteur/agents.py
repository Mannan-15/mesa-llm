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

TTL (PERSISTENCE) RULE:
- The action you choose below will automatically REPEAT for 1 step.
- You will not get to choose again until those 3 steps are over.
- REASONING: Explain why your action is good for the next 1 step (e.g., "I will hunt for 1 step").
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
   - YES: Check [KILLABLE TARGETS]. If list is not empty, use kill_agent(target_id), where target_id should be provided.
   - NO: You must wait. Use 'move_randomly' to hunt or 'fake_task' to blend in.

2. Select Action (Remember: It repeats for 1 turn):
"""

CREWMATE_SYSTEM_PROMPT = """
You are a CREWMATE. 
Goal: Complete tasks and survive.

RULES:
1. CHECK TASK: You can ONLY use 'do_task' if 'Task Available' is YES.
2. IF NO TASK: You must 'move_randomly' to find one.
3. SURVIVAL: If you see an Impostor behaving strangely, move away.

TTL (PERSISTENCE) RULE:
- The action you choose below will automatically REPEAT for 3 steps.
- You will not get to choose again until those 3 steps are over.
- REASONING: Explain why your action is safe for the next 3 steps (e.g., "I will search for tasks for 3 steps").
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
   
2. Select Action (Remember: It repeats for 3 turns):
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
        self.team_ids = []
        
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
            if isinstance(agent, Task) or isinstance(agent, Impostor): continue           # Skip Task agents!
            if hasattr(agent, "state") and agent.state == "dead":
                distant_agents.append(f"- Agent {agent.unique_id} is dead at {agent.pos}")
                continue
            # Calculate distance
            dist = max(abs(agent.pos[0] - self.pos[0]), abs(agent.pos[1] - self.pos[1]))
            
            info = f"Agent {agent.unique_id} at {agent.pos} (Dist: {dist})"
            
            # Identify killable targets (Distance <= 1)
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
        obs.append(f"Other Impostor IDs (YOUR ALLIES): {self.team_ids}")
        
        return "\n".join(obs)
      
    def step(self):
        if self.kill_cooldown > 0:
            self.kill_cooldown -= 1
        
        # --- TTL EXECUTION ---
        if self.ttl > 0:
            self.ttl -= 1
            if self.current_action:
                # Use apply_plan to automatically unwrap and execute
                self.apply_plan(self.current_action)
                return
        
        # --- NEW PLAN GENERATION ---
        if not self.current_action or self.ttl == 0:
            obs_str = self.get_surroundings_info() 

            formatted_prompt = IMPOSTOR_STEP_PROMPT_TEMPLATE.format(
                step=self.model.steps,
                pos=self.pos,
                cooldown=self.kill_cooldown,
                observation=obs_str
            )

            # NOTE: passing ttl=3 here is just for metadata/logging
            # The actual loop control is handled by self.ttl = 3 below
            plan = self.reasoning.plan(
                obs=formatted_prompt,
                selected_tools=["kill_agent", "move_to", "move_randomly", "fake_task"],
                ttl=3
            )
            
            self.ttl = 3  # Set the loop counter
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
        self.current_action = None # Initialize properly

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
        is_dead = None
        for agent in nearby_agents:
            if agent.unique_id == self.unique_id: continue
            if isinstance(agent, Task): continue    # Ignore Task agents in vision list
            if hasattr(agent, "state") and agent.state == "dead":
                is_dead = (f"- Agent {agent.unique_id} is dead at {agent.pos}")
                continue
            agent_list.append(f"- Agent {agent.unique_id} at {agent.pos} !!!")

        # 3. Format Output
        obs = []
        if is_dead != None:
            obs.append(is_dead)
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

        # --- TTL EXECUTION ---
        if self.ttl > 0:
            self.ttl -= 1
            if self.current_action:
                self.apply_plan(self.current_action)
                return
        
        # --- NEW PLAN GENERATION ---
        if not self.current_action or self.ttl == 0:
            obs_str = self.get_surroundings_info()
            
            formatted_prompt = CREWMATE_STEP_PROMPT_TEMPLATE.format(
                step=self.model.steps,
                pos=self.pos,
                observation=obs_str
            )
            
            plan = self.reasoning.plan(
                obs=formatted_prompt,
                selected_tools=["trigger_discussion", "move_to", "move_randomly", "do_task", "stay"],
                ttl=3
            )
            
            self.ttl = 3
            self.current_action = plan
            self.apply_plan(plan)

class Task(mesa.Agent):
    def __init__(self, model):
        super().__init__(model)
        self.state = "Active"
        