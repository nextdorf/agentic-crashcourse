from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

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



app = FastAPI(title='TicTacToe', lifespan=mcp_app.lifespan)
app.state.game = TicTacToe()

@app.get('/')
async def root():
  return {'message': 'Hello World'}

@app.post('/play')
async def play(x: int, y: int, player: int):
  try:
    return app.state.game.play(x, y, player)
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e)) from e

app.mount('/mcp', mcp_app)
