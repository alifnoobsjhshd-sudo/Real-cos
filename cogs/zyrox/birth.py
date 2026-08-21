import discord 
from discord .ext import commands 
from utils.emojis import e as _e


class _birth(commands .Cog ):
    def __init__ (self ,bot ):
        self .bot =bot 

    """Birthday commands"""

    def help_custom (self ):
              emoji = _e('zcircle')
              label ="Birthday Commands"
              description ="Show you the commands of Birthday"
              return emoji ,label ,description 

    @commands.group ()
    async def __Birthday__ (self ,ctx :commands .Context ):
        """`setbirthday` , `listbirthdays` , `birthday`"""
        pass
