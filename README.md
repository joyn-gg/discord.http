# discord.http
Python library that handles interactions from Discord POST requests.

## Installing
> You need **Python >=3.11** to use this library.

Install by using `pip install discord.http` in the terminal.
If `pip` does not work, there are other ways to install as well, most commonly:
- `python -m pip install discord.http`
- `python3 -m pip install discord.http`
- `pip3 install discord.http`

## Quick example
```py <!-- DOCS: quick_example -->
from discord_http import Context, Client, commands

client = Client(
    token="Your bot token here",
    application_id="Bot application ID",
    public_key="Bot public key",
    sync=True
)

@client.command()
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")


@client.command(user_install=True)
@commands.allow_contexts(guild=True, bot_dm=True, private_dm=True)
async def ping2(ctx: Context):
    """ A simple user-install ping command """
    return ctx.response.send_message("Pong!")


client.start()
```

Need further help on how to make Discord API able to send requests to your bot?
Check out [the documentation](https://discordhttp.dev/pages/getting_started.html) for more detailed information.

## Resources
- Documentations
  - [Library documentation](https://discordhttp.dev)
  - [Discord API documentation](https://discord.com/developers/docs/intro)
- [Discord server](https://discord.gg/jV2PgM5MHR)


## Acknowledgements
This library was inspired by [discord.py](https://github.com/Rapptz/discord.py), developed by [Rapptz](https://github.com/Rapptz).
We would like to express our gratitude for their amazing work, which has served as a foundation for this project.
