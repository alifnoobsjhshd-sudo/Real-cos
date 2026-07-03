

import discord 
from discord .ext import commands 

class _ai (commands .Cog ):
    def __init__ (self ,bot ):
        self .bot =bot 

    """AI commands"""

    def help_custom (self ):
        emoji ='<:zai:1448949821611446302>'
        label ="AI Commands"
        description ="Show you the commands of AI"
        return emoji ,label ,description 

    @commands .group ()
    async def __AI__ (self ,ctx :commands .Context ):
        """`ai activate`, `ai deactivate`, `ai analyze`, `ai analyse`, `ai code`, `ai explain`, `ai conversation-clear`, `ai mood-analyzer`, `ai personality`, `ai conversation-stats`, `ai summarize`, `ai ask`, `ai fact`, `ai database-clear`, `ai roleplay-enable`, `ai roleplay-disable`"""
        pass 
