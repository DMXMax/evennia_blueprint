"""
Blueprint

A portable builder's tool that tracks the construction of a MUD area.
Carries a structured build plan, records dbrefs as rooms are built,
and can export a valid .ev batchcmds file.

Usage:
    plan                        - show full build status
    plan add <room name>        - add a room to the plan
    plan desc <room> = <text>   - set the planned description for a room
    plan check <room>           - mark room complete (auto-records dbref)
    plan note <room> = <text>   - attach a note to a room entry
    plan resume                 - teleport to next incomplete room
    plan export                 - output a .ev batchcmds file to screen
    plan finish                 - seal the blueprint (area complete)

The blueprint must be in your inventory to use these commands.
"""

from evennia import Command, CmdSet
from evennia.objects.objects import DefaultObject
from evennia.utils import evtable
from .objects import ObjectParent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _find_room_entry(blueprint, name):
    """Case-insensitive search for a room entry by name or partial match."""
    rooms = blueprint.db.rooms or []
    name_lower = name.strip().lower()
    # exact match first
    for entry in rooms:
        if entry["name"].lower() == name_lower:
            return entry
    # partial match
    for entry in rooms:
        if name_lower in entry["name"].lower():
            return entry
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

class CmdPlan(Command):
    """
    Manage your area blueprint.

    Usage:
        plan                        - show full build status
        plan name <project name>    - set or rename the project
        plan add <room name>        - add a room entry
        plan desc <room> = <text>   - set planned description for a room
        plan check <room>           - mark room complete (records current dbref)
        plan note <room> = <text>   - add a note to a room entry
        plan resume                 - teleport to next incomplete room
        plan export                 - output a .ev batchcmds file
        plan finish                 - mark the area complete
    """

    key = "plan"
    locks = "cmd:holds()"  # must be carrying the blueprint
    help_category = "Building"

    def func(self):
        blueprint = None
        for obj in self.caller.contents:
            if obj.is_typeclass("typeclasses.blueprint.Blueprint", exact=False):
                blueprint = obj
                break
        if not blueprint:
            self.caller.msg("You need to be carrying a Blueprint to use this command.")
            return

        args = self.args.strip()

        if not args:
            self._show_plan(blueprint)
        elif args.lower().startswith("add "):
            self._add_room(blueprint, args[4:].strip())
        elif args.lower().startswith("name "):
            self._set_name(blueprint, args[5:].strip())
        elif args.lower().startswith("desc "):
            self._set_desc(blueprint, args[5:].strip())
        elif args.lower().startswith("check "):
            self._check_room(blueprint, args[6:].strip())
        elif args.lower().startswith("note "):
            self._add_note(blueprint, args[5:].strip())
        elif args.lower().startswith("tag "):
            self._add_tag(blueprint, args[4:].strip())
        elif args.lower() == "resume":
            self._resume(blueprint)
        elif args.lower() == "export":
            self._export(blueprint)
        elif args.lower() == "finish":
            self._finish(blueprint)
        elif args.lower() in ("help", "?"):
            self._show_help()
        else:
            self.caller.msg("Unknown plan command. Use |wplan help|n for usage.")

    def _show_plan(self, blueprint):
        rooms = blueprint.db.rooms or []
        title = blueprint.db.project_name or "Unnamed Project"
        finished = blueprint.db.finished or False

        header = f"|y=== Blueprint: {title} {'[COMPLETE]' if finished else ''} ===|n"
        self.caller.msg(header)

        if not rooms:
            self.caller.msg("  No rooms planned yet. Use |wplan add <room name>|n.")
            return

        anchor = blueprint.db.entrance_dbref
        if anchor:
            self.caller.msg(f"  Entrance room: |w#{anchor}|n")
        self.caller.msg("")

        for i, entry in enumerate(rooms, 1):
            status = "|g[x]|n" if entry.get("complete") else "|r[ ]|n"
            dbref = f"|w#{entry['dbref']}|n" if entry.get("dbref") else "|x#???|n"
            name = entry["name"]
            self.caller.msg(f"  {status} {i}. {name} {dbref}")
            if entry.get("desc"):
                # show truncated desc
                d = entry["desc"]
                preview = d[:60] + "..." if len(d) > 60 else d
                self.caller.msg(f"       |xDesc: {preview}|n")
            if entry.get("tag"):
                self.caller.msg(f"       |yRef: {entry['tag']}|n")
            if entry.get("note"):
                self.caller.msg(f"       |cNote: {entry['note']}|n")

        total = len(rooms)
        done = sum(1 for r in rooms if r.get("complete"))
        self.caller.msg(f"\n  Progress: {done}/{total} rooms complete.")

    def _show_help(self):
        self.caller.msg("""
|y=== Blueprint Commands ===|n

  |wplan|n                        - show full build status
  |wplan help|n                   - show this help
  |wplan name <project name>|n    - set or rename the project
  |wplan add <room name>|n        - add a room entry to the plan
  |wplan desc <room> = <text>|n   - set the planned description for a room
  |wplan check <room>|n           - mark room complete (auto-records current dbref)
  |wplan note <room> = <text>|n   - attach a note to a room entry
  |wplan tag <room> = <tag>|n     - set a module reference tag (e.g. B7, Cave 1A)
  |wplan resume|n                 - teleport to the next incomplete room
  |wplan export|n                 - output a valid .ev batchcmds file
  |wplan finish|n                 - seal the blueprint when area is complete

|xThe blueprint must be in your inventory for these commands to work.|n
""")

    def _set_name(self, blueprint, name):
        if not name:
            self.caller.msg("Usage: plan name <project name>")
            return
        old_name = blueprint.db.project_name or "Unnamed Project"
        blueprint.db.project_name = name
        blueprint.key = f"Blueprint: {name}"
        self.caller.msg(f"Project renamed from |w{old_name}|n to |y{name}|n.")

    def _add_room(self, blueprint, name):
        if not name:
            self.caller.msg("Usage: plan add <room name>")
            return
        rooms = blueprint.db.rooms or []
        # check for duplicate
        if _find_room_entry(blueprint, name):
            self.caller.msg(f"A room named '{name}' already exists in this blueprint.")
            return
        rooms.append({
            "name": name,
            "dbref": None,
            "complete": False,
            "desc": "",
            "note": "",
        })
        blueprint.db.rooms = rooms
        self.caller.msg(f"Added room: |w{name}|n")

    def _set_desc(self, blueprint, args):
        if "=" not in args:
            self.caller.msg("Usage: plan desc <room> = <description>")
            return
        room_name, _, desc_text = args.partition("=")
        room_name = room_name.strip()
        desc_text = desc_text.strip()
        entry = _find_room_entry(blueprint, room_name)
        if not entry:
            self.caller.msg(f"No room matching '{room_name}' found in blueprint.")
            return
        entry["desc"] = desc_text
        blueprint.db.rooms = blueprint.db.rooms  # trigger save
        self.caller.msg(f"Description set for |w{entry['name']}|n.")

    def _check_room(self, blueprint, name):
        if not name:
            self.caller.msg("Usage: plan check <room name>")
            return
        entry = _find_room_entry(blueprint, name)
        if not entry:
            self.caller.msg(f"No room matching '{name}' found in blueprint.")
            return
        # auto-record current location's dbref
        loc = self.caller.location
        if loc:
            entry["dbref"] = loc.id
            entry["complete"] = True
            blueprint.db.rooms = blueprint.db.rooms  # trigger save
            self.caller.msg(
                f"|g[x]|n Marked |w{entry['name']}|n complete. Recorded dbref: |w#{loc.id}|n"
            )
        else:
            self.caller.msg("You don't seem to be in a room. Can't record dbref.")

    def _add_tag(self, blueprint, args):
        if "=" not in args:
            self.caller.msg("Usage: plan tag <room> = <tag>")
            return
        room_name, _, tag_text = args.partition("=")
        room_name = room_name.strip()
        tag_text = tag_text.strip()
        entry = _find_room_entry(blueprint, room_name)
        if not entry:
            self.caller.msg(f"No room matching '{room_name}' found in blueprint.")
            return
        entry["tag"] = tag_text
        blueprint.db.rooms = blueprint.db.rooms
        self.caller.msg(f"Tag |y{tag_text}|n set for |w{entry['name']}|n.")

    def _add_note(self, blueprint, args):
        if "=" not in args:
            self.caller.msg("Usage: plan note <room> = <note text>")
            return
        room_name, _, note_text = args.partition("=")
        room_name = room_name.strip()
        note_text = note_text.strip()
        entry = _find_room_entry(blueprint, room_name)
        if not entry:
            self.caller.msg(f"No room matching '{room_name}' found in blueprint.")
            return
        entry["note"] = note_text
        blueprint.db.rooms = blueprint.db.rooms  # trigger save
        self.caller.msg(f"Note added to |w{entry['name']}|n.")

    def _resume(self, blueprint):
        rooms = blueprint.db.rooms or []
        for entry in rooms:
            if not entry.get("complete"):
                dbref = entry.get("dbref")
                if dbref:
                    target = self.caller.search(f"#{dbref}", global_search=True)
                    if target:
                        self.caller.move_to(target, quiet=True)
                        self.caller.msg(f"Resuming at |w{entry['name']}|n (|w#{dbref}|n).")
                        self.caller.execute_cmd("look")
                        return
                self.caller.msg(
                    f"Next incomplete room: |w{entry['name']}|n - not yet built (no dbref recorded)."
                )
                return
        self.caller.msg("All rooms are complete! Use |wplan finish|n to seal the blueprint.")

    def _export(self, blueprint):
        rooms = blueprint.db.rooms or []
        project = blueprint.db.project_name or "unnamed"
        slug = project.lower().replace(" ", "_")

        lines = []
        lines.append(f"# {'=' * 60}")
        lines.append(f"# Blueprint Export: {project}")
        lines.append(f"# File: world/{slug}.ev")
        lines.append(f"# {'=' * 60}")
        lines.append("")

        entrance_dbref = blueprint.db.entrance_dbref
        if entrance_dbref:
            lines.append(f"# Entrance room: #{entrance_dbref}")
            lines.append(f"@tel #{entrance_dbref}")
            lines.append("")

        for entry in rooms:
            tag = f" [{entry['tag']}]" if entry.get("tag") else ""
            lines.append(f"# --- {entry['name']}{tag} ---")
            dbref = entry.get("dbref")
            if dbref:
                lines.append(f"@tel #{dbref}")
            else:
                alias = entry["name"].lower().replace(" ", "_")
                lines.append(f"@dig {entry['name']};{alias}")
                lines.append(f"@tel {alias}")

            desc = entry.get("desc", "").strip()
            if desc:
                lines.append("@desc")
                lines.append(desc)
            else:
                lines.append("@desc")
                lines.append("(description not yet written)")

            if entry.get("note"):
                lines.append(f"# Note: {entry['note']}")

            lines.append("")

        lines.append(f"# {'=' * 60}")
        lines.append(f"# End of {project}")
        lines.append(f"# {'=' * 60}")

        output = "\n".join(lines)
        self.caller.msg("|y--- Blueprint Export (.ev) ------|n")
        self.caller.msg(output)
        self.caller.msg("|y--- End Export ---|n")

    def _finish(self, blueprint):
        rooms = blueprint.db.rooms or []
        incomplete = [r for r in rooms if not r.get("complete")]
        if incomplete:
            names = ", ".join(r["name"] for r in incomplete)
            self.caller.msg(
                f"|rCannot finish — {len(incomplete)} room(s) still incomplete:|n {names}"
            )
            return
        blueprint.db.finished = True
        project = blueprint.db.project_name or "this area"
        entrance = blueprint.db.entrance_dbref
        self.caller.msg(f"|gBlueprint sealed! {project} is complete.|n")
        if entrance:
            self.caller.msg(f"Consider storing this blueprint in the entrance room (|w#{entrance}|n) as an artifact.")


class BlueprintCmdSet(CmdSet):
    """CmdSet for the Blueprint object."""

    key = "BlueprintCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdPlan())


# ---------------------------------------------------------------------------
# Blueprint Typeclass
# ---------------------------------------------------------------------------

class Blueprint(ObjectParent, DefaultObject):
    """
    A portable builder's blueprint. Carry it to use the 'plan' command.

    Stores a structured build plan for a MUD area including room names,
    dbrefs, descriptions, completion status, and notes. Can export a
    valid Evennia batchcmds (.ev) file.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.project_name = ""
        self.db.entrance_dbref = None
        self.db.rooms = []
        self.db.finished = False
        # Lock: builders can get it, only admin can delete it
        self.locks.add("get:perm(Builder);delete:perm(Admin)")
        self.cmdset.add_default(BlueprintCmdSet, persistent=True)

    def get_display_desc(self, looker, **kwargs):
        """Show a brief status when looked at."""
        rooms = self.db.rooms or []
        project = self.db.project_name or "Unnamed Project"
        done = sum(1 for r in rooms if r.get("complete"))
        total = len(rooms)
        finished = self.db.finished

        status = "|gCOMPLETE|n" if finished else f"|w{done}/{total}|n rooms built"
        return (
            f"A builder's blueprint for |y{project}|n.\n"
            f"Status: {status}\n"
            f"Pick it up and use |wplan|n to manage the build."
        )

    @classmethod
    def create_blueprint(cls, project_name, creator, entrance_room=None):
        """
        Factory method to create a new Blueprint.

        Args:
            project_name (str): Name of the area being built.
            creator (Object): The character creating it (goes to their inventory).
            entrance_room (Room, optional): The entrance room if already dug.

        Returns:
            Blueprint: The new blueprint object.
        """
        from evennia import create_object
        bp = create_object(
            cls,
            key=f"Blueprint: {project_name}",
            aliases=["blueprint", "bp", "plan"],
            location=creator,
        )
        bp.db.project_name = project_name
        if entrance_room:
            bp.db.entrance_dbref = entrance_room.id
        creator.msg(
            f"|gCreated Blueprint for '{project_name}'.|n\n"
            f"Use |wplan add <room name>|n to start planning rooms.\n"
            f"Use |wplan|n to see the current build status."
        )
        return bp
