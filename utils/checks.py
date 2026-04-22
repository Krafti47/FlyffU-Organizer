import discord
from discord.ext import commands

from config import MEMBER_ROLE_NAME, PVP_ROLE_NAME


def require_role(role_name: str):
    async def predicate(ctx: discord.ApplicationContext) -> bool:
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("This command can only be used in a server.")
        if not discord.utils.get(ctx.author.roles, name=role_name):
            raise commands.CheckFailure(
                f"You need the **{role_name}** role to use this command."
            )
        return True
    return commands.check(predicate)


pvp_creator_only = require_role(PVP_ROLE_NAME)
member_only = require_role(MEMBER_ROLE_NAME)
