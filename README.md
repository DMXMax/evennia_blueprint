# Evennia Blueprint

A portable builder's tool for planning and constructing MUD areas in [Evennia](https://www.evennia.com) 6.x.

The Blueprint is an in-game object you carry while building. It stores a structured plan for your area — rooms, descriptions, details, and objects — and tracks progress as you build. When you're done, it exports a valid Evennia batchcmds `.ev` file.

## Features

- Plan an entire area before building a single room
- Track completion room by room, with dbrefs recorded automatically
- Add planned descriptions, details, and notes to each room entry
- Resume a build session after a disconnect with a single command
- Export a valid `.ev` batchcmds file at any time

## Installation

1. Copy `typeclasses/blueprint.py` into your game's `typeclasses/` folder.
2. Reload the server (`evennia reload` or `@reload` in-game as Developer).
3. Create a blueprint in-game (see Usage below).

No changes to `default_cmdsets.py` or other files are required. The Blueprint's commands are attached to the object itself and activate when it's in your inventory.

## Usage

### Creating a Blueprint

Since the Blueprint uses a custom typeclass, create it with two commands:

```
create MyAreaBlueprint
typeclass MyAreaBlueprint = typeclasses.blueprint.Blueprint
plan name My Area Name
get MyAreaBlueprint
```

Or if you have Developer access:

```
@py from typeclasses.blueprint import Blueprint; Blueprint.create_blueprint("My Area", me)
```

### Commands

All commands require the blueprint to be in your inventory.

```
plan                        - show full build status
plan help                   - show command reference
plan name <project name>    - set or rename the project
plan add <room name>        - add a room entry to the plan
plan desc <room> = <text>   - set the planned description for a room
plan check <room>           - mark room complete (auto-records current room's dbref)
plan note <room> = <text>   - attach a note to a room entry
plan resume                 - teleport to the next incomplete room
plan export                 - output a valid .ev batchcmds file
plan finish                 - seal the blueprint when the area is complete
```

### Typical Workflow

**1. Plan the area**
```
plan name Keep Gatehouse
plan add Gatehouse Exterior
plan desc Gatehouse Exterior = The outer face of the gatehouse...
plan add Gatehouse Interior
plan add Guard Room
plan note Guard Room = NPC guards here, patrol script needed
```

**2. Review**
```
plan
plan export
```

**3. Build room by room**
```
dig Gatehouse Exterior;gate_ext = north;n, south;s
tel gate_ext
desc
The outer face of the gatehouse...

plan check Gatehouse Exterior
```

**4. Resume after a disconnect**
```
plan resume
```

**5. Export when done**
```
plan export
plan finish
```

## Recommended Setup

For the best building experience, also install Evennia's built-in **ExtendedRoom** contrib, which adds room details (virtual objects players can look at without creating database entries):

In `typeclasses/rooms.py`:
```python
from evennia.contrib.grid.extended_room import ExtendedRoom
from .objects import ObjectParent

class Room(ObjectParent, ExtendedRoom):
    pass
```

In `commands/default_cmdsets.py`:
```python
from evennia.contrib.grid import extended_room

class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(extended_room.ExtendedRoomCmdSet)
```

Then reload. You can now use `detail <name> = <desc>` in any room instead of creating database objects for purely decorative items.

## Planned Features

- `plan detail <room> + <name>;<alias> = <desc>` — add a detail to a room entry
- `plan object <room> + <name>;<alias> = <desc>` — add an object/NPC to a room entry
- `plan sweep` — sync blueprint descriptions with live room descriptions
- `plan import` — parse an existing `.ev` file into a blueprint

## Compatibility

- Evennia 6.x
- Python 3.11+
