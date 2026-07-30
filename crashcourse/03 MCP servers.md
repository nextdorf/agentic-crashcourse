# MCP Servers

The Model Context Protocol (MCP) provides a standard way for AI clients to connect to external tools and data sources. Instead of teaching every coding agent a custom API integration, an MCP server describes the tools it offers, the parameters they accept, and the results they return.

In this chapter, we will connect the AeroDataBox MCP server to a coding agent, inspect its tools, call one manually, and then let an LLM choose and call the same tool. To follow along, you need a RapidAPI account and an API key with access to AeroDataBox. Keep that key private.

## Connecting the MCP server to your coding agent

**OpenCode:**

```json
{
  "mcp": {
    "RapidAPI/AeroDataBox": {
      "type": "remote",
      "url": "https://mcp.rapidapi.com",
      "headers": {
        "x-api-host": "aerodatabox.p.rapidapi.com",
        "x-api-key": "{env:RAPIDAPI_KEY}"
      },
      "enabled": true
    }
  }
}
```

Note the `"{env:RAPIDAPI_KEY}"`. It reads the API key from the environment variable called `RAPIDAPI_KEY`. However, as of today, there is no way to automatically load the environment variable from a file, but [there is an open GitHub issue](https://github.com/anomalyco/opencode/issues/10458). Alternatively, you can either hard-code `"x-api-key": "YOUR_API_KEY"` or export the environment variable before running OpenCode with `set -a && . .opencode/.env && set +a`.

Hard-coding the key is only okay if you do not share or commit your `opencode.json`. I publish mine on GitHub, so I use an environment variable instead.

**Other coding agents:**

```json
{
  "mcpServers": {
    "rapidapi_aerodatabox": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://mcp.rapidapi.com",
        "--header",
        "x-api-host: aerodatabox.p.rapidapi.com",
        "--header",
        "x-api-key: YOUR_API_KEY"
      ]
    }
  }
}
```

If you get prompted to approve an MCP tool and would like to automatically approve any tool call to this specific MCP server, add the following to `opencode.json`:

```json
{
  "permission": {
    "rapidapi_aerodatabox_*": "allow"
  }
}
```

In general, the tool call name is `[name of MCP server]_[name of tool]`. With `[name of MCP server]_*`, you automatically approve calls to any tool from that server.


## MCP Inspector

Launch `npx @modelcontextprotocol/inspector` (while writing this section the mcp inspector was updated to version 2 and had some bugs, if you want to stay with version 1 use `npx @modelcontextprotocol/inspector@1.0.0` instead). If you run the command for the first time, it might ask you to install the tool. You can find out more about the tool in [the npm registry](https://www.npmjs.com/package/@modelcontextprotocol/inspector) and on [its website](https://modelcontextprotocol.io/docs/tools/inspector). The website also has great resources for developing your own MCP server and understanding the technical side of the protocol. When launched, the output should look something like:

```bash
npm notice run npx
npm notice run 'mcp-inspector'
Starting MCP inspector...
⚙️ Proxy server listening on localhost:6277
🔑 Session token: <SOME_TOKEN>
   Use this token to authenticate requests or set DANGEROUSLY_OMIT_AUTH=true to disable auth

🚀 MCP Inspector is up and running at:
   http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=<SOME_TOKEN>

🌐 Opening browser...
```

The MCP Inspector will serve its frontend as a local website at `http://localhost:6274`. Open it in your browser. To connect to the MCP server, enter:

Key | Value
----|------
Transport Type | HTTP
URL | https://mcp.rapidapi.com
Connection Type | Proxy

Under Authentication/Custom Header, enter:
```json
{
  "x-api-host": "aerodatabox.p.rapidapi.com",
  "x-api-key": "YOUR_API_KEY"
}
```

The parameters you set here are equivalent to the parameters you already saw in the [previous section](#connecting-the-mcp-server-to-your-coding-agent).

In the end, it should look like:

![Configuration of the MCP-Inspector for `npx @modelcontextprotocol/inspector --transport http --server-url https://mcp.rapidapi.com --header x-api-host: aerodatabox.p.rapidapi.com x-api-key: $RAPIDAPI_KEY`](images/03%20inspector.png)

### Tools

The MCP Inspector can be used to look at the endpoints of an MCP server the way an LLM would see them. It also allows you to call the individual tools manually. The main use case is to develop and debug your own MCP server. However, you can also use it to inspect any other MCP server on the internet and better understand how your AI might interact with it.

The AeroDataBox MCP exposes 40 `"tools"`. When the LLM requests the tool list of an MCP server, it gets back a JSON object with the following information about each tool:
* **name** - The MCP equivalent of an API endpoint
* **description** - A prompt for the LLM to better understand that tool. Some MCP servers just copy and paste the API docs of the corresponding API endpoint here. That is lazy and often leads to poor results, as the description and the name of the tool serve as the main context for deciding when and how to call that tool. A better description is written like a prompt with the LLM in mind. At the very least, it should answer what the tool is meant to achieve and help the AI identify what kind of user request probably requires calling this tool.
* **inputSchema** - A definition of the payload that the LLM should send. The parameters can optionally also have descriptions that provide relevant context to the LLM.
* **required** - The required input parameters.

This is what the tool list of the AeroDataBox MCP server looks like:

```json
{
  "tools": [
    {
      "name": "Flight_time__Distance_between_airports__TIER_2",
      "description": "**What is the great circle distance between airports?** \n**What is approximate flight time between airports?**\n**What is the flight time between airports based on history of flights and/or aircraft type?** (machine-learning based)\n\nUse `flightTimeModel = ML01` to get more accurate results based on historical performance of flights on route and aircraft type.\n\nReturns: Distance and approximate flight time between airports, if both airports found.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "_endpoint": {
            "default": "/airports/{codeType}/{codeFrom}/distance-time/{codeTo}",
            "description": "Endpoint: GET /airports/{codeType}/{codeFrom}/distance-time/{codeTo}",
            "hidden": true,
            "type": "string"
          },
          "_method": {
            "default": "GET",
            "description": "HTTP method",
            "hidden": true,
            "type": "string"
          },
          "aircraftName": {
            "default": "Airbus A320",
            "description": "Aircraft type name (free text). If specified and `flightTimeModel` is set to `ML01`, the aircraft type will be attempted to be taken into account in order to provide a more accurate result (experimental). If `flightTimeModel` is set to `Standard`, the value is ignored.",
            "externalDocs": {
              "description": "",
              "url": ""
            },
            "in": "query",
            "type": "string"
          },
          "codeFrom": {
            "default": "LHR",
            "description": "If `codeType` is:\n* `icao`, then this field must be a 4-character ICAO-code of the origin airport (e.g.: EHAM, KLAX, UUEE, etc.);\n* `iata`, then this field must be a 3-character IATA-code of the origin airport (e.g.: AMS, SFO, LAX, etc.).",
            "externalDocs": {
              "description": "",
              "url": ""
            },
            "in": "path",
            "type": "string"
          },
          "codeTo": {
            "default": "LAX",
            "description": "If `codeType` is:\n* `icao`, then this field must be a 4-character ICAO-code of the destination airport (e.g.: EHAM, KLAX, UUEE, etc.);\n* `iata`, then this field must be a 3-character IATA-code of the destination  airport (e.g.: AMS, SFO, LAX, etc.).",
            "externalDocs": {
              "description": "",
              "url": ""
            },
            "in": "path",
            "type": "string"
          },
          "codeType": {
            "description": "Type of code to search airport by (IATA or ICAO)",
            "externalDocs": {
              "description": "",
              "url": ""
            },
            "in": "path",
            "type": "string"
          },
          "flightTimeModel": {
            "default": "Standard,ML01",
            "description": "Model of calculation of the flight time. \n\nPossible values:\n\n`Standard`: Standard model of calculation which takes into account the great circle distance and the average speed of all aircraft typically operating on those distances.\n`ML01`: Experimental machine learning (ML) model, which attempts to provide more accurate prediction of the flight time by taking into account the history of flights on specified route and aircraft type within the recent year.\nThis may come in handy in case when on certain routes flights take significant detours due to extended airspace closures dictated by war conflicts, sanction regulations, etc. This can result in significantly increased flight times comparing to regular estimations.\nOr, some routes generally experience longer delays than other routes of the same distance.\nThis model attempts to take such factors into account and reflect it in the prediction.\nIf a model cannot be applied due to lack of historical and/or aircraft data or prediction is too off set, it automatically fallbacks to `Standard`.",
            "externalDocs": {
              "description": "",
              "url": ""
            },
            "in": "query",
            "type": "string"
          }
        },
        "required": [
          "codeType",
          "codeTo",
          "codeFrom"
        ]
      }
    },
    // 39 other tools
  ]
}
```

_One thing you may note is the sheer amount of text for just one tool. With all 40 tools, the entire tool list would be **2159 lines long!** It's important to keep that in mind, especially for smaller models, because the AI might load that entire JSON object with the tool list into context just to decide whether it makes sense to call a tool. Most LLMs which have been released within the last year can handle that, but with older or very small models you will see that adding more MCP servers will decrease the AI's quality because the context window gets filled with mostly irrelevant information. When writing an MCP server, it is important to balance adding enough context in the description in case the tool should be called and avoiding too much context in case the tool should not be called._

Anyway, we can now inspect that tool by selecting `Flight_time__Distance_between_airports__TIER_2` and filling in the missing fields:

```json
{
  "_endpoint": "/airports/{codeType}/{codeFrom}/distance-time/{codeTo}",
  "_method": "GET",
  "aircraftName": "Airbus A320",
  "codeFrom": "LHR",
  "codeTo": "LAX",
  "codeType": "IATA",
  "flightTimeModel": "Standard,ML01"
}
```

If everything is correct and your API key is valid, you should see the following output:

```json
{
  "from": {
    "icao": "EGLL",
    "iata": "LHR",
    "name": "London Heathrow",
    "shortName": "Heathrow",
    "municipalityName": "London",
    "location": {
      "lat": 51.4706,
      "lon": -0.461941
    },
    "countryCode": "GB",
    "timeZone": "Europe/London"
  },
  "to": {
    "icao": "KLAX",
    "iata": "LAX",
    "name": "Los Angeles",
    "shortName": "Los Angeles",
    "municipalityName": "Los Angeles",
    "location": {
      "lat": 33.9425,
      "lon": -118.408
    },
    "countryCode": "US",
    "timeZone": "America/Los_Angeles"
  },
  "greatCircleDistance": {
    "meter": 8780646.41,
    "km": 8780.65,
    "mile": 5456.04,
    "nm": 4741.17,
    "feet": 28807895.05
  },
  "approxFlightTime": "14:10:00"
}
```

If the LLM receives a response from the MCP server, then the above JSON object will be exactly what is loaded into its context. This is part of the reason why it is generally a good idea to have a separate MCP server alongside an API. Although the API of a service and the MCP server of a service should expose the same functionality, the idiomatic way to access this functionality is very different.

In our coding CLI, we can request the same information in prose:

```opencode
> Whats the approximate flighttime from LHR -> LAX with plane Airbus A320?

+ Thought: Defining distance-time endpoint requirements · 1.2s

⚙rapidapi_aerodatabox_Flight_time__Distance_between_airports__TIER_2 [codeType=iata, codeFrom=LHR, codeTo=LAX, aircraftName=Airbus A320, flightTimeModel=ML01]

The approximate flight time from LHR to LAX on an Airbus A320 is 14 hours 10 minutes.
Distance: approximately 8,781 km.
```

You can see that Codex (GPT-5.6 Luna) correctly figured out that it should call the tool `rapidapi_aerodatabox_Flight_time__Distance_between_airports__TIER_2` and set the parameters `codeType=iata`, `codeFrom=LHR`, `codeTo=LAX`, `aircraftName=Airbus A320`, and `flightTimeModel=ML01`. In our prompt, we did not specify the `codeType` or `flightTimeModel`. Going back to the tool specification, you see:

```json
  "codeType": {
    "description": "Type of code to search airport by (IATA or ICAO)",
    // ...
  },
  "flightTimeModel": {
    "default": "Standard,ML01",
    "description": "Model of calculation of the flight time. \n\nPossible values:\n\n`Standard`: Standard model of calculation which takes into account the great circle distance and the average speed of all aircraft typically operating on those distances.\n`ML01`: Experimental machine learning (ML) model, which attempts to provide more accurate prediction of the flight time by taking into account the history of flights on specified route and aircraft type within the recent year.\nThis may come in handy in case when on certain routes flights take significant detours due to extended airspace closures dictated by war conflicts, sanction regulations, etc. This can result in significantly increased flight times comparing to regular estimations.\nOr, some routes generally experience longer delays than other routes of the same distance.\nThis model attempts to take such factors into account and reflect it in the prediction.\nIf a model cannot be applied due to lack of historical and/or aircraft data or prediction is too off set, it automatically fallbacks to `Standard`.",
    // ...
  }
```

That means it figured out on its own that the provided code is in IATA format, and for the `flightTimeModel`, it decided that `ML01` is a better choice than `Standard`. The reasoning that led to these decisions happened in `+ Thought: Defining distance-time endpoint requirements · 1.2s`. If the inference provider allows it, OpenCode can show the reasoning. OpenAI used to send the reasoning tokens as well but stopped doing so at some point.

For demonstration purposes, let's change the model to something that actually exposes the reasoning and ask the same question in a new chat. In my case, I chose `Kimi K3` via OpenCode Go:

```opencode
> Whats the approximate flighttime from LHR -> LAX with plane Airbus A320?

+ Thought: 6.2s

⚙rapidapi_aerodatabox_Flight_time__Distance_between_airports__TIER_2 [codeType=iata, codeFrom=LHR, codeTo=LAX, aircraftName=Airbus A320, flightTimeModel=ML01]

+ Thought: 4.7s

Based on the flight data, the approximate flight time from LHR (London Heathrow) to LAX (Los Angeles) is:
- Duration: ~14 hours 10 minutes
- Distance: ~8,781 km (5,456 miles)

Note: While you asked about the Airbus A320 specifically, this aircraft typically doesn't operate this route in real-world service. The A320 family has a maximum range of roughly 6,100–6,300 km (depending on variant), which is insufficient for this ~8,800 km transatlantic journey. This route is normally flown by wide-body aircraft such as the Boeing 787, Airbus A350, or Boeing 777. The 14h10m estimate appears to be based on the great-circle distance and standard speed assumptions for this route type.
```

Opening the thoughts reveals the reasoning:

1.  `Thought: 6.2s`
    ```opencode
    The user is asking about the approximate flight time from LHR (London Heathrow) to LAX (Los Angeles) with an Airbus A320. This is a factual question about flight duration.

    I have access to an MCP tool that can calculate flight time and distance between airports. Let me use the rapidapi_aerodatabox_Flight_time__Distance_between_airports__TIER_2 tool to get this information.

    I need to provide:
    - codeType: "iata" (since LHR and LAX are IATA codes)
    - codeFrom: "LHR"
    - codeTo: "LAX"
    - aircraftName: "Airbus A320" (optional, but the user specified it)
    - flightTimeModel: "ML01" would be more accurate as it takes aircraft type into account

    Let me call this tool to get the flight time information.
    ```
2.  `Thought: 4.7s`
    ```opencode
    The API returned:
    - Great circle distance: 8,780.65 km (5,456.04 miles)
    - Approximate flight time: 14:10:00 (14 hours 10 minutes)

    However, I should note that the ML01 model with Airbus A320 might not have been applicable here - the response just shows the standard calculation. An A320 typically wouldn't fly LHR-LAX as it's a narrow-body aircraft with limited range (typically around 6,100 km for the A320neo, less for older models), while this route is about 8,780 km. This route is typically flown by wide-body aircraft like Boeing 787, Airbus A350, or Boeing 777.

    But the user asked specifically about A320, so I should provide the answer while noting that an A320 wouldn't typically operate this route due to range limitations.
    ```

In the first block, we can see Kimi's "inner monologue", which basically prompts itself to provide better output. How a model makes this decision and whether it would or could use reasoning at all are quite model-dependent. The inference provider controls whether OpenCode receives the actual reasoning, a summary, some filler text, or nothing. Interestingly, it decided to put that result into context and highlight that the returned information is probably not factual.

A more detailed overview of tools for a generic MCP server can be found in the [MCP specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#tool). In general, an MCP server may also expose [resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources) and [prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts), but the AeroDataBox MCP does not.


## TicTacToe over MCP
```bash
uv init tictactoe-mcp
```

```bash
cd tictactoe-mcp
uv add fastapi fastmcp uvicorn
uv add --dev ipykernel # For using the Jupyter extension within VS Code
```


```python
class TicTacToe:
  def __init__(self):
    self.board = [[' ' for _ in range(3)] for _ in range(3)]
    self.player1 = 'X'
    self.player2 = 'O'
  def __repr__(self) -> str:
    return '\n-+-+-\n'.join('|'.join(row) for row in self.board)
TicTacToe()
```

Add functionality:

```python
class TicTacToe:
  def __init__(self):
    self.board = [[' ' for _ in range(3)] for _ in range(3)]
    self.player1 = 'X'
    self.player2 = 'O'
    self.next_player = 1
    self.winner = None
  def play(self, x: int, y: int, player: int):
    if self.winner is not None:
      raise ValueError(f'{self.winner} already won')
    if player != self.next_player:
      raise ValueError('Not your turn')
    if x not in range(3) or y not in range(3):
      raise ValueError('Invalid move')
    if self.board[x][y] != ' ':
      raise ValueError('Square already taken')
    self.board[y][x] = self.player1 if player == 1 else self.player2
    if self.check_for_game_over():
      self.winner = f'Player {player}'
    else:
      self.next_player = 2 if player == 1 else 1
    summary = f'Player {player} played at ({x}, {y})'
    summary += ' and won.' if self.winner is not None else f'. Now is Player {self.next_player}\'s turn.'
    result = {
      'board': self.board,
      'next_player': self.next_player,
      'winner': self.winner,
      'summary': summary,
    }
    return result
  def check_for_game_over(self):
    for i in range(3):
      if self.board[i][0] == self.board[i][1] == self.board[i][2] != ' ':
        return True
      if self.board[0][i] == self.board[1][i] == self.board[2][i] != ' ':
        return True
    if self.board[0][0] == self.board[1][1] == self.board[2][2] != ' ':
      return True
    if self.board[0][2] == self.board[1][1] == self.board[2][0] != ' ':
      return True
    return False
```

Let's play a few moves to test it:
```python
b = TicTacToe()
print(b.play(1,1,1)['summary'])
print(b.play(0,2,2)['summary'])
print(b)
```
> ```text
> Player 1 played at (1, 1). Now is Player 2's turn.
> Player 2 played at (0, 2). Now is Player 1's turn.
> ┌─┬─┬─┐
> │ │ │ │
> ├─┼─┼─┤
> │ │X│ │
> ├─┼─┼─┤
> │O│ │ │
> └─┴─┴─┘
> ```

### Super short introduction into FastAPI
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
  return {"message": "Hello World"}
```

```bash
uv run uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000` to see your site.

Visit `http://127.0.0.1:8000/docs` for the swagger page. It is an auto-generated overview of your API. Alternatively, there is also `http://127.0.0.1:8000/redoc` for a Redocs page.

```python
from fastapi import FastAPI

app = FastAPI()
app.state.game = TicTacToe()

@app.post("/play")
async def play(x: int, y: int, player: int):
  return app.state.game.play(x, y, player)
```

When you save, uvicorn will detect the file change and automatically recreate the app. This means state will be lost. In a serious project we handle the state differently and for example store it in a database. But for a quick test, this is fine.

One problem the above snippet has is that errors are not handled correctly. The TicTacToe class has proper error handling but when we do an illegal move the app will just crash. Instead we need to "re-raise" the error as a `HTTPException`. A statuscode 4xx generally tells the client, that the request was not successful:

```python
from fastapi import FastAPI, HTTPException

# ...

@app.post("/play")
async def play(x: int, y: int, player: int):
  try:
    return app.state.game.play(x, y, player)
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
```

In order to add an mcp server next to the fastapi server add the following code:
```python
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

mcp = FastMCP('TicTacToe')
@mcp.tool
def mcp_summarize_game():
  'Returns a summary of the game. Does not change the game state. You should use this to get the current state of the game. Call this tool in the beginning of the game and when the state has changed.'
  return app.state.game.as_dict()

@mcp.tool
def mcp_play(x: int, y: int, player: int):
  'Make a single move'
  try:
    return app.state.game.play(x, y, player)
  except Exception as e:
    raise ToolError(str(e)) from e

mcp_app = mcp.http_app(path='/')


# Add the mcp server's lifespan to your FastAPI app
# This important so the FastAPI knows that it must start and shutdown the MCP server on its own start and shut down
app = FastAPI(title='TicTacToe', lifespan=mcp_app.lifespan)

app.mount('/mcp', mcp_app)
```

and add the following function to the TicTacToe class:

```python
class TicTacToe:
  # ...
  def as_dict(self):
    return {
      'board': self.board,
      'player1': self.player1,
      'player2': self.player2,
      'next_player': self.next_player,
      'winner': self.winner,
    }
```

Now you can instruct the AI to play against you over the browser. Or you can start to instances and let them play together. Just note that with this API layout both you and the AI can simply cheat by making a move for the opposing player as well.

### Inspect with MCP inspector

Like before, run the inspector via `npx @modelcontextprotocol/inspector` (or `npx @modelcontextprotocol/inspector@1.0.0`) and enter:

Key | Value
----|------
Transport Type | HTTP
URL | https://127.0.0.1:8000/mcp/
Connection Type | Proxy

No authetification needed this time.

Change to the tools section and open `http://localhost:8000/docs` in a seperate tab. Verify that the changes you make either on the mcp-inspector or in the swagger interface are visible on the other interface as well. Also taking a look at the terminal output from running `uv run uvicorn main:app --reload` helps to understand what requests are made.

### Pydantic

One think you might wonder is how to actually add proper tool description. What you should see in the mcp-inspector at this point is that the docstring from the python function is visible in the tool-list, but what about the parameters and the return value? The answer is `pydantic`. Pydantic is a library which becomes useful whenever python's [weak typesystem](https://medium.com/@cpave3/understanding-types-static-vs-dynamic-strong-vs-weak-88a4e1f0ed5f) works against you. It is the standard way to do data validation and is used pretty much anywhere where you need to sanitize your input, which is always the case with APIs exposed to the internet. On top of data validation pydantic comes with other niceties as type annotations. Both FastAPI and FastMCP support these type annotions. Add the following code:

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field

# ...

class GameState(BaseModel):
  board: list[list[Literal['X', 'O', ' ']]] = Field(
    description='The three board rows from top to bottom. Each row contains three squares from left to right; a space represents an empty square.'
  )
  player1: Literal['X'] = Field(description='The mark used by Player 1.')
  player2: Literal['O'] = Field(description='The mark used by Player 2.')
  next_player: Literal[1, 2] = Field(description='The player who must make the next legal move.')
  winner: Literal['Player 1', 'Player 2'] | None = Field(
    description='The player who won, or null while the game is still in progress.'
  )

# ...

@mcp.tool(annotations=dict(
  title='Summarize Tic-Tac-Toe Game',
  readOnlyHint=True,
  destructiveHint=False,
  idempotentHint=True,
  openWorldHint=False,
))
def mcp_summarize_game() -> GameState:
  'Returns a summary of the game. Does not change the game state. You should use this to get the current state of the game. Call this tool in the beginning of the game and when the state has changed.'
  return GameState(**app.state.game.as_dict())

@mcp.tool(annotations=dict(
  title='Play Tic-Tac-Toe Move',
  readOnlyHint=False,
  destructiveHint=False,
  idempotentHint=False,
  openWorldHint=False,
))
def mcp_play(
  x: Annotated[int, Field(description='Column from left to right. 0 is the leftmost column.', ge=0, le=2)],
  y: Annotated[int, Field(description='Row from top to bottom. 0 is the top row.', ge=0, le=2)],
  player: Annotated[Literal[1, 2], Field(description='Player making this move. Player 1 uses X; Player 2 uses O.')],
):
  'Make one legal move at zero-indexed coordinates (x, y) and return the updated game state.'
  try:
    return app.state.game.play(x, y, player)
  except Exception as e:
    raise ToolError(str(e)) from e

```

If you now reconnect the mcp-inspector and list all tools you will see all that information. That being said, different mcp clients and coding agents can still decide on their own how much of that information they pass on to the AI. For exmaple as of now (opencode version 1.18.8), most of the information is stripped and all the AI actually sees is:

```json
{
  "name": "my_mcp_mcp_play",
  "description": "Make one legal move at zero-indexed coordinates (x, y) and return the updated game state.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "x": {
        "type": "integer",
        "description": "Column from left to right. 0 is the leftmost column."
      },
      "y": {
        "type": "integer",
        "description": "Row from top to bottom. 0 is the top row."
      },
      "player": {
        "type": "integer",
        "enum": [1, 2],
        "description": "Player making this move. Player 1 uses X; Player 2 uses O."
      }
    },
    "required": ["x", "y", "player"]
  }
}
```
and
```json
{
  "name": "my_mcp_mcp_summarize_game",
  "description": "Returns a summary of the game. Does not change the game state. You should use this to get the current state of the game. Call this tool in the beginning of the game and when the state has changed.",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

Nevertheless, the non-cosmetic annotations can still be useful. For example, as you see above the AI does not know that the board is only 3x3 big from the input-schema alone. So if you instruct it just do an illegal move and play at 5x5 for example, the request will reach the server. But with our new function signature the input data will never see our function body and gets stopped by pydantic. The uvicorn logs show the following error message:

```bash
[07/30/26 15:32:50] WARNING  Invalid arguments for tool 'mcp_play': [
  {
    'type': 'less_than_equal',
    'loc': ('x',),
    'msg': 'Input should be less than or equal to 2',
    'input': 5,
server.py:1325
    'ctx': {'le': 2}
  },
  {
    'type': 'less_than_equal',
    'loc': ('y',),
    'msg': 'Input should be less than or equal to 2',
    'input': 5,
    'ctx': {'le': 2}
  }
]
```

These error messages come from `Field(..., ge=0, le=2)`. If we instead play another illegal move like playing on an occupied square, then the uvicorn logs show the error message propagated from re-raising the ValueError from `TicTacToe.play`

```bash
[07/30/26 15:46:58] Error calling tool 'mcp_play'
```

Equivalently you can also annotate your FastAPI endpoints. You will see the descriptions in the Swagger and Redocs interface but thats rather for debugging and documentation:

```python
from fastapi import FastAPI, HTTPException, Query

# ...

class MoveResult(BaseModel):
  board: list[list[Literal['X', 'O', ' ']]] = Field(
    description='The board after the move, with rows from top to bottom and columns from left to right.'
  )
  next_player: Literal[1, 2] = Field(description='The player who must make the next legal move.')
  winner: Literal['Player 1', 'Player 2'] | None = Field(
    description='The player who won, or null while the game is still in progress.'
  )
  summary: str = Field(description='Short human-readable description of the move outcome.')


@app.get('/summarize')
async def summarize() -> GameState:
  return GameState(**app.state.game.as_dict())


@app.post('/play')
async def play(
  x: Annotated[int, Query(description='Column from left to right. 0 is the leftmost column.', ge=0, le=2)],
  y: Annotated[int, Query(description='Row from top to bottom. 0 is the top row.', ge=0, le=2)],
  player: Annotated[int, Query(description='Player making this move. Player 1 uses X; Player 2 uses O.', ge=1, le=2)],
) -> MoveResult:
  try:
    return MoveResult(**app.state.game.play(x, y, player))
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

```

Visit http://localhost:8000/docs or http://localhost:8000/redoc or download http://localhost:8000/openapi.json to see the changes

### Final touch

We came really far in quickly building a minimal TicTacToe game which can be connected to any LLM and play against it. If you would serve that server on the internet you could also connect it to your ChatGPT or Claude app and play from there. The one last thing that is missing is a proper interface. To keep things simple create a folder `static` and add a static webpage to it. As I know nothing about web development or design I will not give any advice here, but feel free to ask your AI to generate you something for your project (that's how I did it). In order to serve it add the following code to your FastAPI app and enjoy your a nice round Tic Tac Toe by visting `http://localhost:8000`:

```python
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ...

static_path = Path(__file__).parent / 'static'

@app.get('/')
async def root():
  return FileResponse(static_path / 'index.html')

app.mount('/static', StaticFiles(directory=static_path), name='static')
```

**<Add celebration emoji here> It works!** ...kinda. With everything you have learned so far you should be able to improve our minimal version. Maybe add a reset button? Maybe add a better solution for polling the game state? Maybe make sure that one can not make moves for the enemy player? But all of that is beyond this workshop's scope and left as an exercise for the reader :)

![Tic Tac Toe](images/03%20tic-tac-toe.png)


## TinyBI 2
```opencode
use the tinybi mcp and figure the most profitable category-city pairs and the least profitable ones and make a final verdict and where to invest and what to drop in order to maximize profits

[...]

go deeper and do some explorative analysis of the dataset
```

The AI started by asking TinyBI to inspect the active dataset. This provided the available dimensions and measures, the date range, missing values, and the valid chart options without changing the dashboard.

For the first question, the AI split the data by product category and ranked cities by total profit. It created separate charts for the most and least profitable cities in Furniture, Office Supplies, and Technology. This made the strongest and weakest category-city pairs directly comparable instead of mixing city size with product performance.

The follow-up question required moving beyond that first ranking. The AI used TinyBI to explore the dataset from several directions:

1. Compare sales, profit, and profit margin by category and sub-category.
2. Check whether high sales also produced high profit.
3. Break profit down by discount level to identify where otherwise healthy sales became losses.
4. Compare categories and sub-categories across regions, states, cities, and customer segments.
5. Check shipping modes to see whether fulfillment choices explained the losses.
6. Compare yearly category profits to distinguish persistent growth from a one-off result.

The reasoning was to avoid making the verdict from one profitable city or one bad product. The AI looked for patterns that repeated across several dimensions and separated high-revenue products from high-profit products. This revealed that the main problem was not insufficient sales, but aggressive discounting and a small number of weak product-region combinations. Technology and Office Supplies remained strong across years and markets, while Furniture generated substantial sales with comparatively little profit.

This led to the closing words of the [full explorative analysis report](03%20explorative%20analysis%20report.md):

> **Do not maximize profit by chasing more sales. Maximize it by protecting prices, expanding Technology and Office Supplies in proven markets, and removing region-product combinations that generate revenue without profit.**

![Auto generated plots](images/03%20tinybi2%20mcp%20exploration.png)
