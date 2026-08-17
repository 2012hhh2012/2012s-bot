from __future__ import annotations

import math
from typing import Any, Iterable, List, Optional, Mapping

import discord
from discord.ext import commands


def _chunk(iterable: Iterable, size: int) -> Iterable[list]:
    chunk: list = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


class HelpDropdown(discord.ui.Select):
    def __init__(self, categories: List[str]):
        options = [
            discord.SelectOption(label="Home", emoji="🏠", value="home", description="Back to the main menu"),
        ]
        
        emoji_map = {
            "Music": "🎶", "Ai": "🤖", "Fun": "🎮", "Utility": "🛠️",
            "Moderation": "🛡️", "System": "⚙️", "Test": "🧪", "Other": "📁", "Slash": "⚡"
        }
        
        # Limit to 24 categories + Home = 25 (Discord limit)
        for cat in categories[:24]:
            if cat == "Home": continue
            emoji = emoji_map.get(cat, "📁")
            options.append(discord.SelectOption(label=cat, emoji=emoji, value=cat.lower()))

        super().__init__(placeholder="Select a category...", options=options, custom_id="help_dropdown")

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        value = self.values[0]
        if value == "home":
            await view.show_home(interaction)
        else:
            await view.show_category(interaction, value)


class HelpView(discord.ui.LayoutView):
    def __init__(self, help_command: PaginatedHelpCommand, mapping: Mapping[Optional[commands.Cog], List[commands.Command]], slash_commands: List[Any], author: discord.abc.User):
        super().__init__(timeout=180.0)
        self.help_command = help_command
        self.author_id = author.id
        self.mapping = mapping
        self.slash_commands = slash_commands
        
        self.category_data = self._prepare_categories()
        self.current_category = "home"
        self.current_page = 0
        self.message: discord.Message | None = None

        self.dropdown = HelpDropdown(list(self.category_data.keys()))
        self._setup_buttons()

    def _prepare_categories(self) -> dict[str, List[Any]]:
        data = {}
        for cog, cmds in self.mapping.items():
            filtered = [cmd for cmd in cmds if not cmd.hidden]
            if not filtered: continue
            
            if cog:
                module = cog.__module__
                parts = module.split(".")
                if len(parts) >= 2 and parts[0] == "commands":
                    name = parts[1].capitalize()
                else:
                    name = cog.qualified_name
            else:
                name = "Other"
            
            if name not in data:
                data[name] = []
            data[name].extend(filtered)
            
        sorted_data = {}
        for name in sorted(data.keys()):
            sorted_data[name] = sorted(data[name], key=lambda c: c.name)
            
        if self.slash_commands:
            sorted_data["Slash"] = sorted(self.slash_commands, key=lambda c: c.qualified_name)
        return sorted_data

    def _setup_buttons(self):
        self.btn_first = discord.ui.Button(label="⏮", style=discord.ButtonStyle.secondary, custom_id="help_first")
        self.btn_prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.primary, custom_id="help_prev")
        self.btn_next = discord.ui.Button(label="▶", style=discord.ButtonStyle.primary, custom_id="help_next")
        self.btn_last = discord.ui.Button(label="⏭", style=discord.ButtonStyle.secondary, custom_id="help_last")
        self.btn_close = discord.ui.Button(label="✖", style=discord.ButtonStyle.danger, custom_id="help_close")

        self.btn_first.callback = self.go_first
        self.btn_prev.callback = self.go_prev
        self.btn_next.callback = self.go_next
        self.btn_last.callback = self.go_last
        self.btn_close.callback = self.stop_help

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ This help menu is not for you.", ephemeral=True)
            return False
        return True

    def _get_pagination_row(self, total_pages: int) -> discord.ui.ActionRow:
        self.btn_first.disabled = self.current_page <= 0 or total_pages <= 1
        self.btn_prev.disabled = self.current_page <= 0 or total_pages <= 1
        self.btn_next.disabled = self.current_page >= total_pages - 1 or total_pages <= 1
        self.btn_last.disabled = self.current_page >= total_pages - 1 or total_pages <= 1
        return discord.ui.ActionRow(self.btn_first, self.btn_prev, self.btn_next, self.btn_last, self.btn_close)

    async def show_home(self, interaction: discord.Interaction):
        self.current_category = "home"
        self.current_page = 0
        
        self.clear_items()
        container = discord.ui.Container(accent_colour=discord.Colour.blurple())
        container.add_item(discord.ui.TextDisplay("## 2012's Bot Help"))
        container.add_item(discord.ui.Separator())
        
        prefix_list = await self.help_command.get_prefixes()
        prefix_display = " ".join(f"`{p}`" for p in prefix_list)
        
        total_prefix = sum(len(cmds) for cmds in self.category_data.values() if isinstance(cmds[0], commands.Command))
        total_slash = len(self.slash_commands)

        container.add_item(discord.ui.TextDisplay(
            f"Use the dropdown below to explore commands.\n\n"
            f"**Prefixes:** {prefix_display}\n"
            f"**Total Prefix Commands:** `{total_prefix}`\n"
            f"**Total Slash Commands:** `{total_slash}`"
        ))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        
        container.add_item(discord.ui.ActionRow(self.dropdown))
        container.add_item(discord.ui.ActionRow(self.btn_close))
        
        self.add_item(container)
        await interaction.response.edit_message(content=None, embed=None, view=self)

    async def show_category(self, interaction: discord.Interaction, category: str):
        # Find the original case name for display
        original_name = None
        for name in self.category_data.keys():
            if name.lower() == category.lower():
                original_name = name
                break
        
        if not original_name:
            return
            
        self.current_category = original_name  # Store original case
        self.current_page = 0
        await self._send_page(interaction)

    async def _send_page(self, interaction: discord.Interaction):
        data = []
        for name, cmds in self.category_data.items():
            if name.lower() == self.current_category.lower():
                data = cmds
                break
        if not data: return
        
        chunk_size = 12 if isinstance(data[0], commands.Command) else 15
        chunks = list(_chunk(data, chunk_size))
        total_pages = len(chunks)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        current_chunk = chunks[self.current_page]
        
        self.clear_items()
        container = discord.ui.Container(accent_colour=discord.Colour.blurple())
        title = f"## {self.current_category} Commands"
        if total_pages > 1:
            title += f" ({self.current_page + 1}/{total_pages})"
        
        container.add_item(discord.ui.TextDisplay(title))
        container.add_item(discord.ui.Separator())
        
        lines = []
        for cmd in current_chunk:
            if isinstance(cmd, commands.Command):
                lines.append(f"`{cmd.name}` — {cmd.short_doc or 'No description'}")
            else:
                lines.append(f"`/{cmd.qualified_name}` — {cmd.description or 'No description'}")
        
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))
        container.add_item(discord.ui.ActionRow(self.dropdown))
        container.add_item(self._get_pagination_row(total_pages))
        
        self.add_item(container)
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    async def go_first(self, interaction: discord.Interaction):
        self.current_page = 0
        await self._send_page(interaction)

    async def go_prev(self, interaction: discord.Interaction):
        self.current_page -= 1
        await self._send_page(interaction)

    async def go_next(self, interaction: discord.Interaction):
        self.current_page += 1
        await self._send_page(interaction)

    async def go_last(self, interaction: discord.Interaction):
        data = []
        for name, cmds in self.category_data.items():
            if name.lower() == self.current_category.lower():
                data = cmds
                break
        if not data: return
        chunk_size = 12 if isinstance(data[0], commands.Command) else 15
        self.current_page = math.ceil(len(data) / chunk_size) - 1
        await self._send_page(interaction)

    async def stop_help(self, interaction: discord.Interaction):
        layout = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_colour=discord.Colour.blurple())
        container.add_item(discord.ui.TextDisplay("Help menu closed."))
        layout.add_item(container)
        
        self.clear_items()
        await interaction.response.edit_message(view=layout)
        self.stop()

    async def on_timeout(self) -> None:
        if self.message:
            self.clear_items()
            try: await self.message.edit(view=self)
            except: pass


class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={"name": "help", "aliases": ["commands"]})
        self.verify_checks = False
        self.show_hidden = False

    async def send_bot_help(self, mapping):
        slash_commands = [cmd for cmd in self.context.bot.tree.walk_commands() if not getattr(cmd, "hidden", False)]
        view = HelpView(self, mapping, slash_commands, self.context.author)
        
        container = discord.ui.Container(accent_colour=discord.Colour.blurple())
        container.add_item(discord.ui.TextDisplay("## 2012's Bot Help"))
        container.add_item(discord.ui.Separator())
        
        prefix_list = await self.get_prefixes()
        prefix_display = " ".join(f"`{p}`" for p in prefix_list)
        
        total_prefix = sum(len([c for c in cmds if not c.hidden]) for cmds in mapping.values())

        container.add_item(discord.ui.TextDisplay(
            f"Use the dropdown below to explore commands.\n\n"
            f"**Prefixes:** {prefix_display}\n"
            f"**Total Prefix Commands:** `{total_prefix}`\n"
            f"**Total Slash Commands:** `{len(slash_commands)}`"
        ))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        
        container.add_item(discord.ui.ActionRow(view.dropdown))
        container.add_item(discord.ui.ActionRow(view.btn_close))
        
        view.add_item(container)
        view.message = await self.get_destination().send(view=view)

    async def send_command_help(self, command: commands.Command):
        layout = discord.ui.LayoutView(timeout=60.0)
        container = discord.ui.Container(accent_colour=discord.Colour.blurple())
        container.add_item(discord.ui.TextDisplay(f"## Help: {command.name}"))
        container.add_item(discord.ui.Separator())
        
        desc = command.help or "No description provided."
        sig = self.get_command_signature(command)
        
        container.add_item(discord.ui.TextDisplay(f"**Usage:** `{sig}`\n\n**Description:**\n{desc}"))
        
        if command.aliases:
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            container.add_item(discord.ui.TextDisplay(f"**Aliases:** {', '.join(f'`{a}`' for a in command.aliases)}"))
            
        layout.add_item(container)
        await self.get_destination().send(view=layout)

    async def send_cog_help(self, cog: commands.Cog):
        await self.send_bot_help(self.get_bot_mapping())

    async def get_prefixes(self) -> List[str]:
        prefixes = await self.context.bot.get_prefix(self.context.message)
        return [prefixes] if isinstance(prefixes, str) else prefixes

    async def send_error_message(self, error: str):
        layout = discord.ui.LayoutView(timeout=30.0)
        container = discord.ui.Container(accent_colour=discord.Colour.red())
        container.add_item(discord.ui.TextDisplay(f"❌ {error}"))
        layout.add_item(container)
        await self.get_destination().send(view=layout)
