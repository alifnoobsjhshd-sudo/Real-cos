import discord 
from discord .ext import commands 


class _birth(commands .Cog ):
    def __init__ (self ,bot ):
        self .bot =bot 

    """Birthday commands"""

    def help_custom (self ):
              emoji ='<:zcircle:1448964410155470848>'
              label ="Birthday Commands"
              description ="Show you the commands of Birthday"
              return emoji ,label ,description 

    @commands.group ()
    async def __Birthday__ (self ,ctx :commands .Context ):
        """`birthdaysetup` , `setbirthday` , `removebirthday` , `listbirthdays` , `birthday`"""
        pass
