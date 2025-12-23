import mesa
from mesa_llm.llm_agent import LLMAgent
from mesa_llm.memory.st_lt_memory import STLTMemory
from mesa_llm.tools.tool_manager import ToolManager

impostor_tool_manager = ToolManager()
crewmate_tool_manager = ToolManager()

IMPOSTOR_SYSTEM_PROMPT = """
You are the IMPOSTOR on a spaceship.
Your Goal: Eliminate all Crewmates without getting caught.

CORE RULES:
1. KILLING: You have a 'Kill Cooldown'. You can only kill when it is 0.
2. STEALTH: Do NOT kill if other 'alive' Crewmates are nearby (radius 1-2) who might see you.
3. DECEPTION: If you cannot kill, use 'fake_task' to blend in, or 'move' to find isolated targets.
4. SURVIVAL: If you kill, move away immediately.

You have access to tools: 
- 'kill_agent(target_id)': Kills a specific agent in your cell.
- 'move_randomly()': Moves to an adjacent cell.
- 'fake_task()': Stays put and pretends to work.
"""

IMPOSTOR_STEP_PROMPT_TEMPLATE = """
[CURRENT SITUATION]
Time Step: {step}
My Location: {pos}

[INTERNAL STATE]
- Kill Cooldown: {cooldown} (0 means READY TO KILL)

[RADAR / VISION]
The following agents are visible:
{observation}

[TASK]
Analyze the radar. 
- If a Crewmate is in my cell (distance 0) AND Cooldown is 0 AND no witnesses -> KILL.
- If Cooldown > 0 -> MOVE or FAKE_TASK.
- If I have been faking task > 3 turns/ steps -> MOVE.

Select the best tool to use now.
"""

class Impostor(LLMAgent, mesa.discrete_space.CellAgent):
    def __init__(
        self,
        model,
        reasoning,
        llm_model,
        system_prompt = IMPOSTOR_SYSTEM_PROMPT,
        vision = 8,
        internal_state = [],
        step_prompt = IMPOSTOR_STEP_PROMPT_TEMPLATE,
        kill_cooldown = 5
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
        #  we have to see other agents status whether doing task or just walking or going to do task
        
        self.vision = vision 
        self.kill_cooldown = kill_cooldown
        
        self.memory = STLTMemory(
            agent=self,
            display=True,
            llm_model="",
        )
        
        self.tool_manager = impostor_tool_manager
        
    def get_surroundings_info(self):
        # 1. Get the neighbourhood based on vision radius
        # (Assuming your grid system supports this syntax as you described)
        self.neighbourhood = self.cell.get_neighbourhood(radius=self.vision)
        
        # 2. Extract the list of agents
        self.neighbours = self.neighbourhood.agents

        # 3. Formulate the text description
        surroundings_list = []
        
        if not self.neighbours:
            return "You see no other agents nearby."

        for agent in self.neighbours:
            # Skip self if the grid returns the agent itself in the list
            if agent.unique_id == self.unique_id:
                continue
                
            # Here we include the internal state (Role) as requested for now
            info = (
                f"- Agent {agent.unique_id} located at {agent.pos}. "
                f"State: {agent.state}" 
                f"Is Task Location: {self.model.task_layer.data[agent.pos] == 1}"
            )
            surroundings_list.append(info)
        
        is_task_here = self.model.task_layer.data[self.pos] == 1
        
        task_info = ""
        if is_task_here:
            task_info = "\n[IMPORTANT] You are currently standing on a TASK location. You can wait here for a crewmate to arrive or stand still to fake a task here or just move."
        else:
            task_info = "\nThis is not a task location."

        return f"You see the following agents nearby:\n" + "\n".join(surroundings_list) + task_info
     
    def step(self):
        
        if self.kill_cooldown > 0:
            self.kill_cooldown -= 1
        
        
        obs_str = self.get_surroundings_info() 

        formatted_prompt = IMPOSTOR_STEP_PROMPT_TEMPLATE.format(
            step=self.model.schedule.steps,
            pos=self.pos,
            cooldown=self.kill_cooldown,
            observation=obs_str
        )

        plan = self.reasoning.plan(
            obs=formatted_prompt,
            selected_tools=["kill_agent", "move_randomly", "fake_task"]
        )
        
        self.apply_plan(plan)
        
    async def astep(self):
        
        if self.kill_cooldown > 0:
            self.kill_cooldown -= 1
        
        
        obs_str = self.get_surroundings_info() 

        formatted_prompt = IMPOSTOR_STEP_PROMPT_TEMPLATE.format(
            step=self.model.schedule.steps,
            pos=self.pos,
            cooldown=self.kill_cooldown,
            observation=obs_str
        )

        plan = await self.reasoning.plan(
            obs=formatted_prompt,
            selected_tools=["kill_agent", "move_randomly", "fake_task"]
        )
        
        self.apply_plan(plan)
        
        
        
CREWMATE_SYSTEM_PROMPT = """
You are a CREWMATE on a spaceship.
Your Goal: Survive until the timer runs out.

CORE RULES:
1. SURVIVAL: Your primary goal is to stay alive. Avoid suspicious behavior.
2. TASKS: You must complete tasks to keep the ship running. 
   - Use 'do_task()' when you are at a task location.
   - If no task is nearby, use 'move_randomly()' to find one.
3. AWARENESS: Keep an eye on other agents. If someone is following you or acting strangely, move away.
4. TIME LIMIT: The Impostors lose if they don't kill everyone before time runs out. Wasting time is a valid strategy if you are safe.

You have access to tools:
- 'move_randomly()': Moves to an adjacent cell to patrol or flee.
- 'do_task()': Performs a task at your current location (takes 1 turn).
- 'stay()': Do nothing (risky if an Impostor is nearby).
"""

CREWMATE_STEP_PROMPT_TEMPLATE = """
[CURRENT SITUATION]
Time Step: {step}
My Location: {pos}

[RADAR / VISION]
The following agents are visible:
{observation}

[TASK]
Analyze your situation:
1. THREAT CHECK: Is anyone too close? If yes, consider moving away.
2. JOB CHECK: Am I currently doing a task? If yes, continue or finish.
3. DECISION:
   - If safe and idle -> 'do_task' (if tasks available) or 'move_randomly' to look busy.
   - If unsafe -> 'move_randomly' to flee.

Select the best tool to use now.
"""
    
class Crewmate(LLMAgent, mesa.discrete_space.CellAgent):
    def __init__(
        self,
        model,
        reasoning,
        llm_model,
        system_prompt = "",
        vision = 4,
        internal_state = [],
        step_prompt = ""
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
        
        #  we have to see other agents status whether doing task or just walking or going to do task
        self.vision = vision
        self.state = "moving"
        
        self.memory = STLTMemory(
            agent = self,
            display = True,
            llm_model = ""
        )

    def get_surroundings_info(self):
        # Reusing the exact same logic as Impostor for now
        self.neighbourhood = self.cell.get_neighbourhood(radius=self.vision)
        self.neighbours = self.neighbourhood.agents
        
        surroundings_list = []
        if not self.neighbours:
            return "You see no other agents nearby."

        for agent in self.neighbours:
            if agent.unique_id == self.unique_id:
                continue
            
            info = (
                f"- Agent {agent.unique_id} at {agent.pos}. "
                f"(State: {agent.state})" 
            )
            surroundings_list.append(info)
        
        is_task_here = self.model.task_layer.data[self.pos] == 1
        
        task_info = ""
        if is_task_here:
            task_info = "\n[IMPORTANT] You are currently standing on a TASK location. You can perform a task here."
        else:
            task_info = "\nThere is no task at your current location."

        return f"You see the following agents nearby:\n" + "\n".join(surroundings_list) + task_info

    def step(self):
        obs_str = self.get_surroundings_info()
        
        formatted_prompt = CREWMATE_STEP_PROMPT_TEMPLATE.format(
            step=self.model.schedule.steps,
            pos=self.pos,
            observation=obs_str
        )
        
        plan = self.reasoning.plan(
            obs=formatted_prompt,
            selected_tools=["move_randomly", "do_task", "stay"]
        )
        
        self.apply_plan(plan)

    async def astep(self):
        obs_str = self.get_surroundings_info()
        
        formatted_prompt = CREWMATE_STEP_PROMPT_TEMPLATE.format(
            step=self.model.schedule.steps,
            pos=self.pos,
            observation=obs_str
        )
        
        plan = await self.reasoning.plan(
            obs=formatted_prompt,
            selected_tools=["move_randomly", "do_task", "stay"]
        )
        
        self.apply_plan(plan)
        