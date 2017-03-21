from pymtl import *
from collections import deque
from pclib.valrdy import valrdy_to_str
from ValRdyBundle import ValRdyBundle

class TestSource( Updates ):

  def __init__( s, nmsgs = 1, input_ = [] ):
    assert type(input_) == list, "TestSrc only accepts a list of inputs!" 

    s.input_ = deque( input_ ) # deque.popleft() is faster
    s.out = ValRdyBundle( nmsgs )

    @s.update_on_edge
    def up_src():
      if s.out.rdy and s.input_:  s.input_.popleft()
      s.out.val = len(s.input_) > 0
      s.out.msg = [0] * nmsgs if not s.input_ else s.input_[0]

    # The following is equivalent
    # @s.update
    # def up_src_val():
      # if not s.input_:
        # s.msg = [0] * nmsgs
        # s.val = 0
      # else:
        # s.msg = s.input_[0]
        # s.val = 1

    # @s.update
    # def up_src_rdy():
      # if s.rdy and s.input_:
        # s.input_.popleft()

  def done( s ):
    return not s.input_

  def line_trace( s ):
    return s.out.line_trace()

class StreamSource( Updates ):

  def __init__( s, nmsgs = 1 ):
    s.out = ValRdyBundle( nmsgs )
    s.ts  = 0

    @s.update_on_edge
    def up_src():
      s.out.msg = ( s.ts+95827*(s.ts&1), s.ts+(19182)*(s.ts&1) )
      # s.msg = ( 60, 35 )
      s.out.val = 1
      s.ts += 1

  def done( s ):
    return not s.input_

  def line_trace( s ):
    return s.out.line_trace()
