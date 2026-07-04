"""
/upload emojis   — uploads the bot's custom emoji images to the current server.
/delete emojis   — deletes a given number of custom emojis from the server
                   (animated or non-animated, your choice — no link to the upload system).
/emoji_status    — shows which branches have been uploaded.

Branches (each ≤ 45 emojis so any un-boosted server can hold them):
  core     — status, navigation, actions
  features — bot features, security, tech
  music    — music, presence, special
  badges   — Discord badges & extras
"""

from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio

from utils.emojis import BRANCHES, reload_store, get_store

EMOJI_DIR   = "assets/emojis"
STORE_PATH  = "data/emoji_store.json"

BRANCH_DESCRIPTIONS = {
    "core":     "Status, navigation & action emojis (45 emojis)",
    "features": "Bot features, security & tech emojis (45 emojis)",
    "music":    "Music, presence & special emojis (45 emojis)",
    "badges":   "Discord badges & extras (17 emojis)",
}

ACCENT = 0xFFD700
GREEN  = 0x2ECC71
RED    = 0xFF0000


# ── Cog ───────────────────────────────────────────────────────────────────────

class EmojiUpload(commands.Cog):
    """Slash commands to manage the bot's emoji pack on a server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /upload ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="upload",
        description="Upload Zyrox's custom emoji pack to this server."
    )
    @app_commands.describe(
        branch="Which branch of emojis to upload (each branch has up to 45 emojis)."
    )
    @app_commands.choices(branch=[
        app_commands.Choice(name="core    — Status, navigation & action emojis",    value="core"),
        app_commands.Choice(name="features — Bot features, security & tech emojis", value="features"),
        app_commands.Choice(name="music   — Music, presence & special emojis",      value="music"),
        app_commands.Choice(name="badges  — Discord badges & extras",               value="badges"),
    ])
    @app_commands.default_permissions(manage_emojis=True, administrator=True)
    async def upload(
        self,
        interaction: discord.Interaction,
        branch: app_commands.Choice[str],
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                f"❌ You need **Administrator** permission to upload emojis.",
                ephemeral=True,
            )

        branch_name = branch.value
        emoji_names = BRANCHES.get(branch_name, [])

        if not emoji_names:
            return await interaction.response.send_message(
                f"❌ Unknown branch `{branch_name}`.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=False, thinking=True)

        existing  = {em.name: em for em in guild.emojis}

        to_upload = [n for n in emoji_names if os.path.exists(f"{EMOJI_DIR}/{n}.png")]
        missing   = [n for n in emoji_names if not os.path.exists(f"{EMOJI_DIR}/{n}.png")]

        # Emojis that already exist on the server will be replaced (delete → re-upload).
        # Only truly new emojis consume a free slot.
        new_names      = [n for n in to_upload if n not in existing]
        replace_names  = [n for n in to_upload if n in existing]
        free_slots     = guild.emoji_limit - len(existing)

        # How many new (non-replacing) emojis we can fit
        allowed_new    = free_slots
        capped_new     = new_names[:allowed_new]
        skipped_no_slot = new_names[allowed_new:]   # ones we simply have no room for

        final_to_upload = replace_names + capped_new   # replacements are always attempted

        if not final_to_upload:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title=f"❌ No Emojis to Upload",
                    description=(
                        f"All {len(to_upload)} emojis in branch **{branch_name}** already exist "
                        f"on this server AND there are no free slots for new ones.\n"
                        f"Use `/delete_emojis` to free up space first."
                    ),
                    color=RED,
                )
            )

        progress_embed = discord.Embed(
            title=f"⏳ Uploading **{branch_name}** emoji pack…",
            description=(
                f"Replacing **{len(replace_names)}** existing + uploading **{len(capped_new)}** new emojis.\n"
                f"Server slots: `{free_slots}` free / `{guild.emoji_limit}` total\n\n"
                f"⚠️ This replaces old versions — please wait."
            ),
            color=ACCENT,
        )
        progress_embed.set_footer(text="Do not run other emoji commands until this finishes.")
        msg = await interaction.followup.send(embed=progress_embed)

        uploaded: dict[str, str] = {}
        failed:   list[str]      = []
        replaced: list[str]      = []

        for name in final_to_upload:
            img_path = f"{EMOJI_DIR}/{name}.png"

            # Step 1: delete the old emoji if it exists so we can upload the new image
            if name in existing:
                try:
                    await existing[name].delete(reason=f"Replacing with updated Zyrox emoji pack image")
                    await asyncio.sleep(0.4)
                except discord.Forbidden:
                    failed.append(name)
                    continue
                except discord.HTTPException:
                    pass  # already gone — continue to upload

            # Step 2: upload the new image from disk
            try:
                with open(img_path, "rb") as f:
                    image_bytes = f.read()

                emoji = await guild.create_custom_emoji(
                    name=name,
                    image=image_bytes,
                    reason=f"Zyrox emoji pack — branch: {branch_name}",
                )
                uploaded[name] = f"<:{emoji.name}:{emoji.id}>"
                if name in existing:
                    replaced.append(name)
                await asyncio.sleep(0.6)
            except discord.Forbidden:
                failed.append(name)
                break
            except discord.HTTPException as ex:
                if ex.status == 429:
                    await asyncio.sleep(5)
                    try:
                        with open(img_path, "rb") as f:
                            image_bytes = f.read()
                        emoji = await guild.create_custom_emoji(
                            name=name,
                            image=image_bytes,
                            reason=f"Zyrox emoji pack — branch: {branch_name} (retry)",
                        )
                        uploaded[name] = f"<:{emoji.name}:{emoji.id}>"
                        if name in existing:
                            replaced.append(name)
                    except Exception:
                        failed.append(name)
                elif "maximum" in str(ex).lower():
                    break
                else:
                    failed.append(name)

        _save_uploaded(uploaded)

        new_count      = len([n for n in uploaded if n not in existing])
        replaced_count = len([n for n in uploaded if n in existing])
        fail_count     = len(failed)

        result_embed = discord.Embed(
            title=f"✅ Emoji Pack Installed — **{branch_name}**",
            color=GREEN if fail_count == 0 else ACCENT,
        )
        if replaced_count:
            result_embed.add_field(name=f"✅ Replaced",
                                   value=f"`{replaced_count}` old emojis swapped with new design",
                                   inline=True)
        if new_count:
            result_embed.add_field(name=f"➕ Added",
                                   value=f"`{new_count}` brand-new emojis uploaded",
                                   inline=True)
        if fail_count:
            result_embed.add_field(name=f"❌ Failed",
                                   value=f"`{fail_count}` could not be uploaded",
                                   inline=True)
        if skipped_no_slot:
            result_embed.add_field(name=f"⚠️ No Slot",
                                   value=f"`{len(skipped_no_slot)}` skipped — server emoji limit reached",
                                   inline=False)
        if missing:
            result_embed.add_field(name=f"⚠️ Missing files",
                                   value=f"`{len(missing)}` emoji images not found on disk",
                                   inline=False)

        preview_names = list(uploaded.keys())[:20]
        if preview_names:
            preview = "  ".join(uploaded[n] for n in preview_names)
            result_embed.add_field(name="Preview", value=preview, inline=False)

        remaining_branches = [b for b in BRANCHES if b != branch_name]
        result_embed.add_field(
            name=f"ℹ️ Next Steps",
            value=(
                f"➡️ Upload remaining branches:\n"
                + "\n".join(
                    f"  `/upload emojis branch:{b}`  — {BRANCH_DESCRIPTIONS[b]}"
                    for b in remaining_branches
                )
                + f"\n\n✅ The bot now uses these emojis automatically!"
            ),
            inline=False,
        )

        result_embed.set_footer(text=f"Zyrox X • Emoji Pack • Branch: {branch_name}")
        await msg.edit(embed=result_embed)

    # ── /delete emojis ────────────────────────────────────────────────────────

    @app_commands.command(
        name="delete_emojis",
        description="Delete a number of custom emojis from this server."
    )
    @app_commands.describe(
        amount="How many emojis to delete (1–250).",
        emoji_type="Delete animated emojis, non-animated emojis, or both.",
    )
    @app_commands.choices(emoji_type=[
        app_commands.Choice(name="Non-animated only",  value="static"),
        app_commands.Choice(name="Animated only",      value="animated"),
        app_commands.Choice(name="Both (all)",         value="both"),
    ])
    @app_commands.default_permissions(manage_emojis=True, administrator=True)
    async def delete_emojis(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 250],
        emoji_type: app_commands.Choice[str],
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        if not interaction.user.guild_permissions.manage_emojis:
            return await interaction.response.send_message(
                f"❌ You need **Manage Emojis** permission to delete emojis.",
                ephemeral=True,
            )

        # Filter server emojis by chosen type
        all_emojis = list(guild.emojis)
        etype = emoji_type.value

        if etype == "static":
            pool = [em for em in all_emojis if not em.animated]
            type_label = "non-animated"
        elif etype == "animated":
            pool = [em for em in all_emojis if em.animated]
            type_label = "animated"
        else:
            pool = all_emojis
            type_label = "all"

        if not pool:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"⚠️ This server has no **{type_label}** emojis to delete.",
                    color=ACCENT,
                ),
                ephemeral=True,
            )

        to_delete = pool[:amount]

        # Confirmation view
        confirm_view = _ConfirmView(interaction.user)
        confirm_embed = discord.Embed(
            title=f"⚠️ Confirm Emoji Deletion",
            description=(
                f"You are about to permanently delete **{len(to_delete)}** "
                f"**{type_label}** emojis from **{guild.name}**.\n\n"
                f"**This action cannot be undone.**\n"
                f"Press **Confirm** to proceed, or **Cancel** to abort."
            ),
            color=0xFF6600,
        )
        confirm_embed.set_footer(text="This prompt expires in 30 seconds.")
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

        await confirm_view.wait()

        if not confirm_view.confirmed:
            cancelled_embed = discord.Embed(
                description=f"❌ Emoji deletion **cancelled**.",
                color=RED,
            )
            return await interaction.edit_original_response(embed=cancelled_embed, view=None)

        # Start deletion
        progress_embed = discord.Embed(
            title=f"⏳ Deleting emojis…",
            description=f"Deleting **{len(to_delete)}** {type_label} emojis. Please wait.",
            color=ACCENT,
        )
        await interaction.edit_original_response(embed=progress_embed, view=None)

        deleted: list[str] = []
        failed:  list[str] = []

        for em in to_delete:
            try:
                await em.delete(reason=f"Bulk emoji deletion by {interaction.user} via /delete_emojis")
                deleted.append(em.name)
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                failed.append(em.name)
                break
            except discord.HTTPException as ex:
                if ex.status == 429:
                    await asyncio.sleep(5)
                    try:
                        await em.delete(reason="Bulk emoji deletion (retry)")
                        deleted.append(em.name)
                    except Exception:
                        failed.append(em.name)
                else:
                    failed.append(em.name)

        result_embed = discord.Embed(
            title=f"✅ Emoji Deletion Complete",
            color=GREEN if not failed else ACCENT,
        )
        result_embed.add_field(
            name=f"✅ Deleted",
            value=f"`{len(deleted)}` {type_label} emojis removed",
            inline=True,
        )
        if failed:
            result_embed.add_field(
                name=f"❌ Failed",
                value=f"`{len(failed)}` could not be deleted",
                inline=True,
            )
        result_embed.add_field(
            name=f"ℹ️ Server Slots",
            value=f"`{len(guild.emojis)}` used / `{guild.emoji_limit}` total after deletion",
            inline=False,
        )
        result_embed.set_footer(text=f"Requested by {interaction.user} • Zyrox X")
        await interaction.edit_original_response(embed=result_embed, view=None)

    # ── /emoji_export ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="emoji_export",
        description="Export the current emoji store as JSON for the EMOJI_STORE_JSON env var.",
    )
    @app_commands.default_permissions(administrator=True)
    async def emoji_export(self, interaction: discord.Interaction):
        store = get_store()
        if not store:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ No Emojis Stored",
                    description=(
                        "No emoji data found. Run `/upload emojis branch:<name>` first.\n\n"
                        "After uploading all branches, run `/emoji_export` again to get the JSON."
                    ),
                    color=ACCENT,
                ),
                ephemeral=True,
            )

        store_json = json.dumps(store, ensure_ascii=False)

        # Also save to the project root so the user can download it from Replit
        export_path = "emoji_store.json"
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(store_json)

        embed = discord.Embed(
            title="📦 Emoji Store Export",
            description=(
                "**The JSON has been saved to `emoji_store.json` in the project root.**\n\n"
                "Download it from the Replit file tree, copy the full contents, and set it as the "
                "`EMOJI_STORE_JSON` environment variable on Render. This keeps emojis across redeploys."
            ),
            color=GREEN,
        )
        embed.add_field(
            name="ℹ️ Stored entries",
            value=f"`{len(store)}` emoji IDs configured",
            inline=True,
        )
        embed.add_field(
            name="📁 File saved",
            value=f"`{export_path}`",
            inline=True,
        )
        embed.set_footer(text="Zyrox X • Emoji Persistence")

        # Send JSON as a text file attachment too so it's easy to grab
        json_bytes = store_json.encode("utf-8")
        file = discord.File(
            fp=__import__("io").BytesIO(json_bytes),
            filename="emoji_store.json",
        )
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    # ── /emoji_status ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="emoji_status",
        description="Check which emoji branches have been uploaded to this server.",
    )
    @app_commands.default_permissions(administrator=True)
    async def emoji_status(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Use in a server.", ephemeral=True)

        store = _load_store()
        server_emoji_names = {em.name for em in guild.emojis}

        embed = discord.Embed(
            title=f"⚙️ Emoji Pack Status — {guild.name}",
            color=ACCENT,
        )

        for branch_name, emoji_list in BRANCHES.items():
            present = [n for n in emoji_list if n in server_emoji_names]
            total   = len(emoji_list)
            frac    = len(present) / total if total else 0
            bar     = "█" * int(frac * 10) + "░" * (10 - int(frac * 10))
            status  = f"`[{bar}]` {len(present)}/{total}"
            embed.add_field(name=f"🧩 {branch_name}", value=status, inline=False)

        embed.add_field(
            name=f"ℹ️ Stored emoji IDs",
            value=f"`{len(store)}` emojis configured from previous uploads",
            inline=False,
        )
        embed.add_field(
            name=f"☁️ Server emoji slots",
            value=f"`{len(guild.emojis)}` used / `{guild.emoji_limit}` total",
            inline=False,
        )
        embed.set_footer(text="Run /upload emojis branch:<name> to upload a branch.")
        await interaction.response.send_message(embed=embed)


# ── Confirmation UI ───────────────────────────────────────────────────────────

class _ConfirmView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member):
        super().__init__(timeout=30)
        self.author    = author
        self.confirmed = False

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Only the command author can confirm this.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.confirmed = False
        self.stop()
        await interaction.response.defer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_store() -> dict:
    try:
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_uploaded(new_emojis: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    store = _load_store()
    store.update(new_emojis)
    with open(STORE_PATH, "w") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    reload_store()


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiUpload(bot))
