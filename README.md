<a href="https://ibb.co/QjmCZXmh"><img src="https://i.ibb.co/x85fy35w/kvantwars.png" alt="kvantwars" border="0"></a>
# KvantWars Project

The project consists of a website and a game running on it.

## Structure

* venv — Virtual environment for the project
* app — Application folder

## Website

### Features:

1. Users can submit a registration request for admin approval  
   The request includes:  
   - Login  
   - Password  
   - Full name  
   - Age  
   - Faction selection from the list of existing factions

2. Resources  
   A faction can track its resources, income, etc.

3. Actions  
   Each faction can perform **one action of each type** per turn:  
   - Capture a territory (cell)  
   - Build a building on owned territory  
   - Upgrade a built or captured building on owned territory  
   - Defend a cell  
   - Send resources to another faction

4. Logs  
   Faction can view what actions they performed during the current turn

## Game

### Gameplay

1. The game is displayed on the main page for everyone, but only authorized faction members can interact with it.
2. Turns are **global** (shared for all players).
3. Each turn lasts **30 seconds** (this duration will be increased later).
4. Each faction performs its actions during the turn. If a faction doesn't make a move — it simply skips the turn.
5. At the end of the turn, all faction actions are resolved, resources for the next turn are awarded based on buildings + base income.

### Map

The map consists of a 7×7 grid of green squares.

1. Each faction starts in one of the corners of the map.
2. Every square has a gray border; if it belongs to a faction, the border changes to that faction's color.
3. To capture a square, it must be connected by owned territories to the faction's castle.
4. If a faction loses a connecting territory between the castle and other lands, those disconnected territories become neutral (buildings remain but become neutral).
5. When capturing a territory with a building, the building starts belonging to the faction and generates corresponding income.

### Factions

Currently, there are 4 factions in the game:

- **IT-Kvantum**
- **Design-Kvantum**
- **Robo-Kvantum**
- **Aero-Kvantum**

Each has its own primary color used throughout the game.

### Resources

The game features 5 resource types and ways to obtain them besides the base per-turn income:

- **Gold**: from every cell owned by the faction
- **Ore**: from buildings specialized in this resource
- **Stone**: from buildings specialized in this resource
- **Wood**: from buildings specialized in this resource
- **Warriors**: can be purchased with Gold

#### Base resource income

Base per-turn generation per cell (depends on resource type and buildings):

1. **Wood**  
   - Starting amount: 10 units  
   - Base income: 1 wood per turn  
   - Sawmill: +3 wood per turn, +50% per level after the first

2. **Ore**  
   - Starting amount: 10 units  
   - Base income: 1 ore per turn  
   - Mine: +3 ore per turn, +50% per level after the first

3. **Stone**  
   - Starting amount: 10 units  
   - Base income: 1 stone per turn  
   - Quarry: +3 stone per turn, +50% per level after the first

4. **Gold**  
   - Starting amount: 15 units  
   - Base income: 1 gold per turn + 1 gold per owned cell

5. **Warriors**  
   - Starting amount: 2 units  
   - Base income: none

#### Recruiting & upkeep of warriors

1. **Recruitment**  
   - Cost per warrior: 5 gold  
   - Max warriors per turn: 10 (limited by available gold and barracks)

2. **Upkeep**  
   - Cost per warrior per turn: 0.5 gold  
   - If a faction lacks gold for upkeep, some warriors will die

### Buildings

Available buildings and their functions:

- **Castle**: starting point of the faction (located in a corner), unique per faction
- **Sawmill**: increases wood income per turn
- **Mine**: increases ore income per turn
- **Quarry**: increases stone income per turn
- **Warehouse**: increases maximum resource storage capacity (+20 to max for all resources)
- **Barracks**: increases maximum number of warriors

Neutral buildings are defended by N barbarians.

#### Building upgrades & bonuses

Any building (except the castle) can be upgraded up to level 3 (starting at level 1).

- Upgrade level icon appears in the top-left corner of the territory cell
- When a building becomes neutral, it resets to level 1

Upgrades:

- **Sawmill**: each level above 1 increases production by 50% (lvl 2: +4.5, lvl 3: +6 per turn)
- **Mine**: each level above 1 increases production by 50% (lvl 2: +4.5, lvl 3: +6 per turn)
- **Quarry**: each level above 1 increases production by 50% (lvl 2: +4.5, lvl 3: +6 per turn)
- **Warehouse**: each upgrade gives +50 to max storage for all resources
- **Barracks**: each upgrade gives +10 to max warriors

### Points of Interest on the map and barbarian defense (TO BE DESIGNED & IMPLEMENTED)

## Technology Stack

### Backend

- **Flask**
- **SQLAlchemy**  
  Additional libraries may be added during development

### Frontend

- **HTML + CSS + JS**
- **Bootstrap**
- **Jinja2**
