import discord
import re
import inspect
from discord.ext import commands as _commands
from discord.ext.commands import CheckFailure, CommandError
from utils.Tools import *
from utils.branding import DEFAULT_COLOR, DEFAULT_BRANDING
from utils.emojis import e as _e


def _is_noop_bare_group(cmd_obj) -> bool:
    """True if cmd_obj is a Group whose own body does nothing but redirect
    to help when invoked without a subcommand (e.g. `>ticket`, `>media`
    alone). Such bare invocations are not functional on their own and
    should not be listed/runnable from the help menu."""
    if not isinstance(cmd_obj, _commands.Group):
        return False
    try:
        src = inspect.getsource(cmd_obj.callback)
    except (OSError, TypeError):
        return False

    src_lines = src.splitlines()
    def_index = next(
        (i for i, l in enumerate(src_lines) if re.match(r'\s*(async\s+)?def\s', l)),
        None,
    )
    if def_index is None:
        return False

    body_lines = []
    for raw_line in src_lines[def_index + 1:]:
        line = raw_line.strip()
        if not line or line.startswith('"""') or line.startswith("'''") or line.startswith("#"):
            continue
        body_lines.append(line)

    if not body_lines:
        return False

    return all(
        re.search(r'send_help\s*\(', line)
        or re.search(r'reset_cooldown\s*\(', line)
        or line.startswith(("if ", "else", "elif "))
        for line in body_lines
    )


def _is_bare_group_pattern(clean: str, bot) -> bool:
    """True if `clean` refers to a top-level group command with no
    subcommand word, and that group is a help-only no-op when run bare."""
    parts = clean.split()
    if len(parts) != 1:
        return False
    cmd_obj = bot.get_command(parts[0])
    return _is_noop_bare_group(cmd_obj)


# ── Command-invocation Modal ───────────────────────────────────────────────────

async def _check_can_run(cmd, ctx) -> bool:
    """Return True only if the command's full check pipeline passes for ctx.
    Catches CheckFailure and any other errors, always failing closed."""
    try:
        return await cmd.can_run(ctx)
    except (CheckFailure, CommandError):
        return False
    except Exception:
        return False


class CommandModal(discord.ui.Modal):
    """Modal for commands that require parameters."""

    def __init__(self, cmd_display: str, params: list, ctx, command_obj):
        super().__init__(title=f"Run: {cmd_display}"[:45])
        self.ctx = ctx
        self.command_obj = command_obj
        self.param_names: list[str] = []

        for param_name, param in params[:5]:
            is_required = param.default is param.empty
            self.add_item(discord.ui.TextInput(
                label=param_name.replace("_", " ").title()[:45],
                placeholder=f"Enter {param_name}…",
                required=is_required,
                style=discord.TextStyle.short,
                max_length=200,
            ))
            self.param_names.append(param_name)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Build a pre-filled command string from the collected inputs and show it
        to the user so they can copy-paste and run it themselves.

        We intentionally do NOT call the command callback directly here —
        that would bypass discord.py's type converters (discord.Member,
        discord.TextChannel, etc.) and produce runtime errors or wrong behaviour.
        Instead we construct a ready-to-use command string and display it.
        """
        await interaction.response.defer(ephemeral=True)

        prefix = getattr(self.ctx, "prefix", ">")
        raw_inputs = [
            child.value
            for child in self.children
            if isinstance(child, discord.ui.TextInput)
        ]

        # Build the pre-filled invocation string
        parts = [f"{prefix}{self.command_obj.qualified_name}"]
        for value in raw_inputs:
            if value:
                # Wrap multi-word values in quotes so the parser handles them correctly
                parts.append(f'"{value}"' if " " in value else value)

        cmd_str = " ".join(parts)

        from utils.emojis import e as _e
        await interaction.followup.send(
            f"{_e('ztick')} Your command is ready — copy and paste it into chat:\n"
            f"```\n{cmd_str}\n```",
            ephemeral=True,
        )


# ── Command-runner Dropdown ────────────────────────────────────────────────────

class CommandRunDropdown(discord.ui.Select):
    """Per-page dropdown that lets the user invoke a command from the help menu."""

    def __init__(self, ctx, cmd_entries: list, row: int = 3):
        """
        cmd_entries: list of (raw_name, display_label, description, is_slash)
        """
        self.ctx = ctx

        if cmd_entries:
            options = [
                discord.SelectOption(
                    label=display[:100],
                    description=(desc or "No description")[:100],
                    value=f"{raw}||{is_slash}",
                )
                for raw, display, desc, is_slash in cmd_entries[:25]
            ]
            disabled = False
            placeholder = "Use a Command…"
        else:
            options = [discord.SelectOption(label="Navigate to a category first", value="__none__")]
            disabled = True
            placeholder = "Select a category to see commands"

        super().__init__(
            placeholder=placeholder,
            min_values=1, max_values=1,
            options=options,
            disabled=disabled,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )

        value = self.values[0]
        if value == "__none__":
            return await interaction.response.defer()

        raw_name, is_slash_str = value.rsplit("||", 1)
        is_slash = (is_slash_str == "True")
        bot = self.ctx.bot
        prefix = getattr(self.ctx, "prefix", ">")

        # ── Slash command ──────────────────────────────────────────────────────
        if is_slash:
            slash_cmd = discord.utils.get(bot.tree.get_commands(), name=raw_name.split()[0])
            desc = f"\n-# {slash_cmd.description}" if slash_cmd and slash_cmd.description else ""
            return await interaction.response.send_message(
                f"Use in Discord: `/{raw_name}`{desc}", ephemeral=True
            )

        # ── Prefix/hybrid command ──────────────────────────────────────────────
        cmd = bot.get_command(raw_name)
        if cmd is None:
            return await interaction.response.send_message(
                f"Use: `{prefix}{raw_name}`", ephemeral=True
            )

        params = [
            (name, param)
            for name, param in cmd.clean_params.items()
            if name not in ("self", "ctx")
        ]

        if not params:
            # No params – enforce checks then invoke
            try:
                await interaction.response.defer(ephemeral=True)
                try:
                    last_msg = interaction.channel.last_message
                    ctx = await bot.get_context(last_msg) if last_msg else self.ctx
                except Exception:
                    ctx = self.ctx
                ctx.author = interaction.user
                ctx.channel = interaction.channel

                # ── Fail closed: run the command's full check pipeline ────────
                from utils.emojis import e as _e
                if not await _check_can_run(cmd, ctx):
                    return await interaction.followup.send(
                        f"{_e('zcross')} You don't have permission to use `{prefix}{cmd.qualified_name}`.",
                        ephemeral=True,
                    )

                await ctx.invoke(cmd)
                try:
                    await interaction.followup.send(f"{_e('ztick')} Command executed!", ephemeral=True)
                except Exception:
                    pass
            except Exception:
                try:
                    await interaction.followup.send(
                        f"Use: `{prefix}{cmd.qualified_name}`", ephemeral=True
                    )
                except Exception:
                    pass
        else:
            # Has params – show modal (modal also enforces can_run before executing)
            modal = CommandModal(cmd.qualified_name, params, self.ctx, cmd)
            await interaction.response.send_modal(modal)


# ── Category Dropdown ──────────────────────────────────────────────────────────

class Dropdown(discord.ui.Select):

    def __init__(self, ctx, options, placeholder="Choose a Category for Help", row=None):
        super().__init__(
            placeholder=placeholder,
            min_values=1, max_values=1,
            options=options,
            row=row,
        )
        self.invoker = ctx.author

    async def callback(self, interaction: discord.Interaction):
        if self.invoker == interaction.user:
            index = self.view.find_index_from_select(self.values[0])
            if not index:
                index = 0
            await self.view.set_page(index, interaction)
        else:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )


# ── Main View ──────────────────────────────────────────────────────────────────

class View(discord.ui.View):

    def __init__(
        self,
        mapping: dict,
        ctx,
        homeembed: discord.Embed,
        ui: int,
        branding: dict = None,
    ):
        super().__init__(timeout=None)
        self.mapping = mapping
        self.ctx = ctx
        self.home = homeembed
        self.index = 0
        self.buttons = None
        self.current_page = 0
        self.branding = branding or {
            "branding_name": DEFAULT_BRANDING,
            "embed_color": DEFAULT_COLOR,
            "embed_thumbnail": None,
            "embed_banner": None,
        }
        # Cache of page_index → cmd_entries for the command runner
        self._page_commands: dict[int, list] = {}
        self._cmd_runner: CommandRunDropdown | None = None

        self.options, self.embeds, self.total_pages = self.gen_embeds()

        if ui == 0:
            self.add_item(Dropdown(ctx=self.ctx, options=self.options))
        elif ui == 1:
            self.buttons = self.add_buttons()
        elif ui == 2:
            self.buttons = self.add_buttons()
            mid_point = len(self.options) // 2
            # Keep the two top-level menus meaningful instead of relying only
            # on cog load order.  These categories are deliberately pinned to
            # the menu requested by the bot's public help layout.
            main_labels = {
                "Leveling Commands",
                "Ticket",
                "Logging Commands",
            }
            extra_labels = {"Poll Commands"}
            options_1 = []
            options_2 = []
            for index, option in enumerate(self.options):
                if option.label in main_labels:
                    options_1.append(option)
                elif option.label in extra_labels:
                    options_2.append(option)
                elif index < mid_point:
                    options_1.append(option)
                else:
                    options_2.append(option)
            if options_1:
                self.add_item(Dropdown(ctx=self.ctx, options=options_1, placeholder="Main Commands", row=1))
            if options_2:
                self.add_item(Dropdown(ctx=self.ctx, options=options_2, placeholder="Extra Commands", row=2))
            # Command runner starts disabled on home page
            self._refresh_cmd_runner(0)
        else:
            self.buttons = self.add_buttons()
            self.add_item(Dropdown(ctx=self.ctx, options=self.options))

    # ── Buttons ────────────────────────────────────────────────────────────────

    def add_buttons(self):
        self.homeB = discord.ui.Button(label="", emoji=_e("rewind1"),    style=discord.ButtonStyle.secondary)
        self.homeB.callback = self.home_callback

        self.backB = discord.ui.Button(label="", emoji=_e("next"),       style=discord.ButtonStyle.secondary)
        self.backB.callback = self.back_callback

        self.quitB = discord.ui.Button(label="", emoji=_e("delete"),     style=discord.ButtonStyle.danger)
        self.quitB.callback = self.quit_callback

        self.nextB = discord.ui.Button(label="", emoji=_e("icons_next"), style=discord.ButtonStyle.secondary)
        self.nextB.callback = self.next_callback

        self.lastB = discord.ui.Button(label="", emoji=_e("forward"),    style=discord.ButtonStyle.secondary)
        self.lastB.callback = self.last_callback

        buttons = [self.homeB, self.backB, self.quitB, self.nextB, self.lastB]
        for button in buttons:
            self.add_item(button)
        return buttons

    async def home_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True)
        await self.set_page(0, interaction)

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True)
        current_page = self.index - 1 if self.index > 0 else len(self.embeds) - 1
        await self.set_page(current_page, interaction)

    async def quit_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True)
        await self.quit(interaction)

    async def next_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True)
        current_page = self.index + 1 if self.index < len(self.embeds) - 1 else 0
        await self.set_page(current_page, interaction)

    async def last_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True)
        await self.set_page(len(self.embeds) - 1, interaction)

    # ── Index helpers ──────────────────────────────────────────────────────────

    def find_index_from_select(self, value):
        """Map a dropdown label back to its embed page index.

        Must mirror the cog iteration order in gen_embeds() exactly:
        - Skip Roleplay cogs
        - Skip merged cogs (PlaylistCog etc.) — they have no standalone page
        """
        i = 0
        used_labels: set[str] = set()
        for cog in self.get_cogs():
            if cog.__class__.__name__ == "Roleplay":
                continue
            # Skip cogs that are merged into another page (no standalone dropdown entry)
            if cog.__class__.__name__ in self._MERGE_INTO:
                continue
            if "help_custom" in dir(cog):
                _, label, _ = cog.help_custom()
                original_label = label
                counter = 1
                while label in used_labels:
                    label = f"{original_label} {counter}"
                    counter += 1
                used_labels.add(label)
                if label == value or value.startswith(original_label + " "):
                    return i + 1
                i += 1
        return 0

    def get_cogs(self):
        return list(self.mapping.keys())

    # ── Command-runner helpers ─────────────────────────────────────────────────

    # Cogs whose commands are merged into another page (kept in sync with gen_embeds logic)
    _MERGE_INTO: dict[str, str] = {"PlaylistCog": "Music", "InviteLeaderboardCog": "inviteTracker"}

    def _collect_page_commands(self, cog, extra_cogs: list = None) -> list:
        """Return (raw_name, display_label, description, is_slash) for commands on a cog page.
        Pass extra_cogs to also include commands from cogs merged into this page."""
        entries: list = []
        seen: set[str] = set()

        def _lookup_desc(cmd_name: str) -> str:
            cmd_obj = self.ctx.bot.get_command(cmd_name)
            if cmd_obj:
                return (cmd_obj.short_doc or cmd_obj.help or "")[:80]
            return ""

        def _process_cog(c):
            for command in c.get_commands():
                docstring = command.help or ""
                cmd_patterns = re.findall(r'`([^`]+)`', docstring)
                for pattern in cmd_patterns:
                    stripped = pattern.strip()
                    if not stripped:
                        continue
                    is_slash = stripped.startswith("/")
                    clean = re.sub(r'\s*[@#<>\[\]]\S*', '', stripped.lstrip("/").lstrip(">")).strip()
                    if not clean or clean in seen:
                        continue
                    if not is_slash and _is_bare_group_pattern(clean, self.ctx.bot):
                        continue
                    seen.add(clean)
                    display = f"{'/' if is_slash else '>'}{clean}"
                    desc = _lookup_desc(clean.split()[0]) if not is_slash else ""
                    entries.append((clean, display, desc, is_slash))

            for slash_item in getattr(c, "__cog_app_commands__", []):
                sub_cmds = getattr(slash_item, "commands", None)
                if sub_cmds:
                    # It's a group — expand sub-commands
                    for sub in sub_cmds:
                        full_name = f"{slash_item.name} {sub.name}"
                        if full_name in seen:
                            continue
                        seen.add(full_name)
                        desc = (sub.description or "")[:80]
                        entries.append((full_name, f"/{full_name}", desc, True))
                else:
                    name = slash_item.name
                    if name in seen:
                        continue
                    seen.add(name)
                    desc = (slash_item.description or "")[:80]
                    entries.append((name, f"/{name}", desc, True))

        _process_cog(cog)
        for extra in (extra_cogs or []):
            _process_cog(extra)

        return entries

    def _refresh_cmd_runner(self, page_index: int):
        """Remove old command runner and attach a fresh one for page_index.

        Uses the same filtered/merged cog list as gen_embeds() so page indices
        stay perfectly in sync after PlaylistCog is merged into the Music page.
        """
        if self._cmd_runner is not None:
            try:
                self.remove_item(self._cmd_runner)
            except Exception:
                pass

        if page_index not in self._page_commands:
            if page_index == 0:
                self._page_commands[0] = []
            else:
                all_help_cogs = [
                    c for c in self.get_cogs()
                    if c.__class__.__name__ != "Roleplay" and "help_custom" in dir(c)
                ]
                # Mirror gen_embeds: skip merged cogs from the standalone list
                help_cogs = [
                    c for c in all_help_cogs
                    if c.__class__.__name__ not in self._MERGE_INTO
                ]
                # Build a lookup of merged cog objects keyed by target class name
                merged_by_target: dict[str, list] = {}
                for c in all_help_cogs:
                    target = self._MERGE_INTO.get(c.__class__.__name__)
                    if target:
                        merged_by_target.setdefault(target, []).append(c)

                idx = page_index - 1
                if 0 <= idx < len(help_cogs):
                    target_cog = help_cogs[idx]
                    extra = merged_by_target.get(target_cog.__class__.__name__, [])
                    self._page_commands[page_index] = self._collect_page_commands(target_cog, extra)
                else:
                    self._page_commands[page_index] = []

        self._cmd_runner = CommandRunDropdown(
            ctx=self.ctx,
            cmd_entries=self._page_commands[page_index],
            row=3,
        )
        self.add_item(self._cmd_runner)

    # ── Embed generation ───────────────────────────────────────────────────────

    def gen_embeds(self):
        options, embeds = [], []
        total_pages = 0
        used_labels: set[str] = set()

        # Home page
        options.append(discord.SelectOption(label="Home", emoji=_e("icons_home"), description=""))
        embeds.append(self.home)
        total_pages += 1
        used_labels.add("Home")

        help_cogs = [
            c for c in self.get_cogs()
            if c.__class__.__name__ != "Roleplay" and "help_custom" in dir(c)
        ]

        # ── Identify cogs that should be merged into another cog's page ───────
        # PlaylistCog is merged into Music; it gets no standalone dropdown entry.
        # InviteLeaderboardCog is merged into inviteTracker; no standalone entry.
        _cogs_to_merge: dict[str, object] = {}   # class_name → cog object
        _merge_target: dict[str, str] = {}        # class_name → target class_name
        for cog in help_cogs:
            if cog.__class__.__name__ == "PlaylistCog":
                _cogs_to_merge["PlaylistCog"] = cog
                _merge_target["PlaylistCog"]  = "Music"
            elif cog.__class__.__name__ == "InviteLeaderboardCog":
                _cogs_to_merge["InviteLeaderboardCog"] = cog
                _merge_target["InviteLeaderboardCog"]   = "inviteTracker"

        for cog in help_cogs:
            # Skip cogs that are merged into another page
            if cog.__class__.__name__ in _cogs_to_merge:
                continue

            emoji_str, label, description = cog.help_custom()
            emoji_str = emoji_str.strip()  # remove accidental trailing spaces
            original_label = label

            counter = 1
            while label in used_labels:
                label = f"{original_label} {counter}"
                counter += 1
            used_labels.add(label)

            # Missing entries render without an emoji; never use a Unicode or
            # hardcoded custom-emoji fallback from another server.
            emoji_display = emoji_str

            options.append(discord.SelectOption(
                label=label,
                emoji=emoji_display or None,
                description=description,
            ))

            # ── Category embed ─────────────────────────────────────────────────
            embed = discord.Embed(
                title=f"{emoji_display + ' ' if emoji_display else ''}{original_label}",
                color=self.branding["embed_color"],
            )

            cmd_lines: list[str] = []

            for command in cog.get_commands():
                docstring = command.help or ""
                # Split on section headers like __**Section Name**__
                parts = re.split(r'(__\*\*.+?\*\*__)', docstring)
                for part in parts:
                    if re.match(r'__\*\*.+?\*\*__', part):
                        # Section header — convert and add as a separator line
                        title = re.sub(r'__\*\*(.+?)\*\*__', r'\1', part).strip()
                        cmd_lines.append(f"\n**» {title}**")
                    else:
                        self._append_cmd_lines(part, emoji_display, cmd_lines)

            # Slash commands directly on this cog
            for slash_cmd in getattr(cog, "__cog_app_commands__", []):
                desc = (slash_cmd.description or "No description")[:80]
                n = sum(1 for l in cmd_lines if not l.startswith("\n"))
                cmd_lines.append(
                    f"`{n + 1}.` {emoji_display} `/` `{slash_cmd.name}` — {desc}"
                )

            # ── Merge-in any cogs that target this cog ─────────────────────────
            for merge_cls, target_cls in _merge_target.items():
                if target_cls != cog.__class__.__name__:
                    continue
                merged_cog = _cogs_to_merge[merge_cls]
                m_emoji, m_label, _ = merged_cog.help_custom()
                cmd_lines.append(f"\n**» {m_label}**")

                # Prefix/hybrid commands from the merged cog (rare but possible)
                for command in merged_cog.get_commands():
                    docstring = command.help or ""
                    parts = re.split(r'(__\*\*.+?\*\*__)', docstring)
                    for part in parts:
                        if re.match(r'__\*\*.+?\*\*__', part):
                            sec_title = re.sub(r'__\*\*(.+?)\*\*__', r'\1', part).strip()
                            cmd_lines.append(f"\n**» {sec_title}**")
                        else:
                            self._append_cmd_lines(part, emoji_display, cmd_lines)

                # Slash commands / groups from the merged cog
                for slash_item in getattr(merged_cog, "__cog_app_commands__", []):
                    # If it's a Group (has sub-commands), expand them
                    sub_cmds = getattr(slash_item, "commands", None)
                    if sub_cmds:
                        for sub in sub_cmds:
                            desc = (sub.description or "No description")[:80]
                            cmd_lines.append(
                                f"`0.` {emoji_display} `/` `{slash_item.name} {sub.name}` — {desc}"
                            )
                    else:
                        desc = (slash_item.description or "No description")[:80]
                        cmd_lines.append(
                            f"`0.` {emoji_display} `/` `{slash_item.name}` — {desc}"
                        )

            # Re-number all lines properly
            numbered = self._renumber_lines(cmd_lines)

            # Add to embed, splitting at 1024-char field boundary
            if numbered:
                chunk = ""
                field_num = 1
                for line in numbered:
                    if len(chunk) + len(line) + 1 > 1020:
                        embed.add_field(
                            name=f"Commands{'' if field_num == 1 else ' (continued)'}",
                            value=chunk.strip() or "—",
                            inline=False,
                        )
                        chunk = line + "\n"
                        field_num += 1
                    else:
                        chunk += line + "\n"
                if chunk.strip():
                    embed.add_field(
                        name=f"Commands{'' if field_num == 1 else ' (continued)'}",
                        value=chunk.strip(),
                        inline=False,
                    )
            else:
                embed.add_field(name="Commands", value="*No commands listed.*", inline=False)

            embeds.append(embed)
            total_pages += 1

        self.home.set_footer(
            text=(
                f"• Help page 1/{total_pages} | "
                f"Requested by: {self.ctx.author.display_name} | "
                f"{self.branding['branding_name']}"
            ),
            icon_url=self.ctx.bot.user.display_avatar.url,
        )
        return options, embeds, total_pages

    def _append_cmd_lines(self, text: str, emoji_display: str, lines: list[str]):
        """Parse backtick-quoted commands from text and append formatted numbered lines."""
        cmd_patterns = re.findall(r'`([^`]+)`', text)
        for pattern in cmd_patterns:
            stripped = pattern.strip()
            if not stripped:
                continue
            is_slash = stripped.startswith("/")
            # Remove leading prefix indicators and user/channel hints
            clean = re.sub(r'\s*[@#<>\[\]]\S*', '', stripped.lstrip("/").lstrip(">")).strip()
            if not clean:
                continue
            if not is_slash and _is_bare_group_pattern(clean, self.ctx.bot):
                continue

            prefix_char = "/" if is_slash else ">"
            # Look up description from actual command
            base_cmd = clean.split()[0]
            desc = ""
            if not is_slash:
                cmd_obj = self.ctx.bot.get_command(base_cmd)
                if cmd_obj:
                    # Try subcommand too
                    if " " in clean:
                        sub_part = clean.split(None, 1)[1].split()[0]
                        if hasattr(cmd_obj, "all_commands") and sub_part in cmd_obj.all_commands:
                            cmd_obj = cmd_obj.all_commands[sub_part]
                    desc = (cmd_obj.short_doc or cmd_obj.help or "")[:80]

            n = len(lines) + 1
            desc_part = f" — {desc}" if desc else ""
            lines.append(
                f"`{n}.` {emoji_display} `{prefix_char}` `{clean}`{desc_part}"
            )

    def _renumber_lines(self, lines: list[str]) -> list[str]:
        """Re-number `N.` counters while preserving section header lines."""
        result: list[str] = []
        counter = 1
        for line in lines:
            if line.startswith("\n**»") or line.startswith("**»"):
                result.append(line)
            else:
                renumbered = re.sub(r'^`\d+\.`', f'`{counter}.`', line)
                result.append(renumbered)
                counter += 1
        return result

    # ── Page navigation ────────────────────────────────────────────────────────

    async def quit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def to_page(self, page: int, interaction: discord.Interaction):
        if not self.index + page < 0 or not self.index + page > len(self.options):
            await self.set_index(page)
            embed = self.embeds[self.index]
            embed.set_footer(
                text=(
                    f"• Help page {self.index + 1}/{self.total_pages} | "
                    f"Requested by: {self.ctx.author.display_name} | "
                    f"{self.branding['branding_name']}"
                ),
                icon_url=self.ctx.bot.user.display_avatar.url,
            )
            await interaction.response.edit_message(embed=embed, view=self)

    async def set_page(self, page: int, interaction: discord.Interaction):
        # Guard against out-of-bounds indices (e.g. from stale dropdown values)
        page = max(0, min(page, len(self.embeds) - 1))
        self.index = page
        self.current_page = page
        # Refresh command runner whenever we switch pages (ui=2 only)
        if self._cmd_runner is not None:
            self._refresh_cmd_runner(page)
        await self.to_page(0, interaction)

    async def set_index(self, page):
        self.index += page
        if self.buttons:
            self.homeB.disabled = (self.index == 0)
            self.backB.disabled = (self.index == 0)
            self.nextB.disabled = (self.index == len(self.options) - 1)
            self.lastB.disabled = (self.index == len(self.options) - 1)

    async def set_last_page(self, interaction: discord.Interaction):
        await self.set_page(len(self.options) - 1, interaction)
