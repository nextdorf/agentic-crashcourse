from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field


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
    if self.board[y][x] != ' ':
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

  def as_dict(self):
    return {
      'board': self.board,
      'player1': self.player1,
      'player2': self.player2,
      'next_player': self.next_player,
      'winner': self.winner,
    }

  def __repr__(self) -> str:
    # return '\n-+-+-\n'.join('|'.join(row) for row in self.board)
    top = '┌─┬─┬─┐'
    bottom = '└─┴─┴─┘'
    between1 = '├─┼─┼─┤'
    between2 = '│{}│{}│{}│'
    main = f'\n{between1}\n'.join(between2.format(*row) for row in self.board)
    full = f'{top}\n{main}\n{bottom}'
    return full
TicTacToe()


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


class MoveResult(BaseModel):
  board: list[list[Literal['X', 'O', ' ']]] = Field(
    description='The board after the move, with rows from top to bottom and columns from left to right.'
  )
  next_player: Literal[1, 2] = Field(description='The player who must make the next legal move.')
  winner: Literal['Player 1', 'Player 2'] | None = Field(
    description='The player who won, or null while the game is still in progress.'
  )
  summary: str = Field(description='Short human-readable description of the move outcome.')


mcp = FastMCP('TicTacToe')
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
) -> MoveResult:
  'Make one legal move at zero-indexed coordinates (x, y) and return the updated game state.'
  try:
    return MoveResult(**app.state.game.play(x, y, player))
  except ValueError as exc:
    raise ToolError(str(exc)) from exc

mcp_app = mcp.http_app(path='/')



app = FastAPI(title='TicTacToe', lifespan=mcp_app.lifespan)
app.state.game = TicTacToe()
static_path = Path(__file__).parent / 'static'

@app.get('/')
async def root():
  return FileResponse(static_path / 'index.html')

@app.get('/summarize')
async def summarize() -> GameState:
  return GameState(**app.state.game.as_dict())


@app.post('/reset')
async def reset() -> GameState:
  app.state.game = TicTacToe()
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

app.mount('/mcp', mcp_app)
app.mount('/static', StaticFiles(directory=static_path), name='static')
