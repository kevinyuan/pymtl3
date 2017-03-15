from pymtl import *
from collections import deque

class TestSource( UpdatesConnection ):

  def __init__( s, input_ ):
    assert type(input_) == list, "TestSrc only accepts a list of inputs!" 

    s.input_ = deque( input_ ) # deque.popleft() is faster
    s.out = ValuePort(int)

    @s.update
    def up_src():
      if not s.input_:
        s.out = 0
      else:
        s.out = s.input_.popleft()

    s.add_constraints(
      U(up_src) < RD(s.out), # model wire behavior
    )

  def done( s ):
    return not s.input_

  def line_trace( s ):
    return "%s" % s.out
