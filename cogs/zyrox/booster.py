import discord 
from discord .ext import commands 
from utils.emojis import e as _e


class __boost(commands .Cog ):
    def __init__ (self ,bot ):
        self .bot =bot 

    """Boost commands"""

    def help_custom (self ):
              emoji = _e('boost')
              label ="Boost Commands"
              description ="Show you the commands of boost"
              return emoji ,label ,description 

    @commands .group ()
    async def __Boost__ (self ,ctx :commands .Context ):
        """`boost setup` , `boost message` , `boost channel` , `boostrole` , `boost config`"""
        pass
