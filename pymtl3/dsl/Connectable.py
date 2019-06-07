"""
========================================================================
Connectable.py
========================================================================
Wires, ports, and interfaces, all inherited from Connectable.

Author : Shunning Jiang
Date   : Apr 16, 2018
"""
from __future__ import absolute_import, division, print_function

from collections import deque

from pymtl3.datatypes import Bits, mk_bits

from .errors import InvalidConnectionError
from .NamedObject import DSLMetadata, NamedObject


class Connectable(object):
  # I've given up maintaining adjacency list or disjoint set locally since
  # we need to easily disconnect things

  # Public API

  def get_host_component( s ):
    try:
      return s._dsl.host
    except AttributeError:
      try:
        host = s
        while not host.is_component():
          host = host.get_parent_object() # go to the component
        s._dsl.host = host
        return s._dsl.host
      except AttributeError:
        raise NotElaboratedError()

# Checking if two slices/indices overlap
def _overlap( x, y ):
  if isinstance( x, int ):
    if isinstance( y, int ):  return x == y
    else:                     return y.start <= x < y.stop
  else: # x is slice
    if isinstance( y, int ):  return x.start <= y < x.stop
    else:
      if x.start <= y.start:  return y.start < x.stop
      else:                   return x.start < y.stop

# internal class for connecting signals and constants, not named object
class Const( Connectable ):
  def __init__( s, Type, v, parent ):
    s._dsl = DSLMetadata()
    s._dsl.Type = Type
    s._dsl.const = v
    s._dsl.parent_obj = parent

  def __repr__( s ):
    return "{}({})".format( str(s._dsl.Type.__name__), s._dsl.const )

  def get_parent_object( s ):
    try:
      return s._dsl.parent_obj
    except AttributeError:
      raise NotElaboratedError()

  def get_sibling_slices( s ):
    return []

  def is_component( s ):
    return False

  def is_signal( s ):
    return False

  def is_interface( s ):
    return False

class Signal( NamedObject, Connectable ):

  def __init__( s, Type ):
    # TODO
    if isinstance( Type, int ):
      raise Exception("Use actual type instead of int (it is deprecated).")
    s._dsl.Type = Type
    s._dsl.type_instance = None

    s._dsl.slice  = None # None -- not a slice of some wire by default
    s._dsl.slices = {}
    s._dsl.top_level_signal = None

  def inverse( s ):
    pass

  def __getattr__( s, name ):
    if name.startswith("_"): # private variable
      return super( Signal, s ).__getattribute__( name )

    if name not in s.__dict__:
      # Shunning: we move this from __init__ to here for on-demand type
      #           checking when the __getattr__ is indeed used.
      if s._dsl.type_instance is None:
        # Yanghui: this would break if another Type indeed has an nbits
        #          attribute.
        # try:  Type.nbits
        # except AttributeError: # not Bits type

        # FIXME: check if Type is actually a type?
        Type = s._dsl.Type
        if not issubclass( Type, Bits ):
          s._dsl.type_instance = Type()

      obj = getattr( s._dsl.type_instance, name )

      # We handle three cases here:
      # 1. If the object is list, we recursively generate lists of signals
      # 2. If the object is Bits, we use the Bits type
      # 3. Otherwise we just go for obj.__class__
      # Note that BitsN is a type now. 2 and 3 are actually unified.

      Q = deque( [ (obj, [], s, False) ] )

      while Q:
        u, indices, parent, parent_is_list = Q.popleft()
        cls = u.__class__

        if cls is list:
          x = []
          for i, v in enumerate( u ):
            Q.append( ( v, indices+[i], x, True ) )

        else:
          x = s.__class__( cls )
          x._dsl.type_instance = u
          x._dsl.parent_obj = s
          x._dsl.top_level_signal = s._dsl.top_level_signal

          x._dsl.my_name   = name + "".join([ "[{}]".format(y) for y in indices ])
          x._dsl.full_name = s._dsl.full_name + "." + x._dsl.my_name

        if parent_is_list:
          parent.append( x )
        else:
          parent.__dict__[ name ] = x

    return s.__dict__[ name ]

  def __setitem__( s, idx, v ):
    pass # I have to override this to support a[0:1] |= b

  def __getitem__( s, idx ):
    # Turn index into a slice
    if isinstance( idx, int ):
      sl = slice( idx, idx+1 )
    elif isinstance( idx, slice ):
      sl = idx
    else: assert False, "What the hell?"

    sl_tuple = (sl.start, sl.stop)

    if sl_tuple not in s.__dict__:
      x = s.__class__( mk_bits( sl.stop - sl.start) )
      x._dsl.parent_obj = s
      x._dsl.top_level_signal = s

      sl_str = "[{}:{}]".format( sl.start, sl.stop )

      x._dsl.my_name   = s._dsl.my_name + sl_str
      x._dsl.full_name = s._dsl.full_name + sl_str

      x._dsl.slice       = sl
      s.__dict__[ sl_tuple ] = s._dsl.slices[ sl_tuple ] = x

    return s.__dict__[ sl_tuple ]

  def default_value( s ):
    return s._dsl.Type()

  #-----------------------------------------------------------------------
  # Public APIs (only can be called after elaboration)
  #-----------------------------------------------------------------------

  def is_component( s ):
    return False

  def is_signal( s ):
    return True

  def is_input_value_port( s ):
    return False

  def is_output_value_port( s ):
    return False

  def is_wire( s ):
    return False

  def is_interface( s ):
    return False

  # Note: We currently define a leaf signal as int/Bits type signal, as
  #       opposed to BitStruct or normal Python object. A sliced signal is
  #       not a leaf signal. A non-leaf signal cannot be sliced or be a
  #       sliced signal.

  def is_leaf_signal( s ):
    return ( issubclass( s._dsl.Type, Bits ) and not s.is_sliced_signal() ) or \
           (Type is int)

  def get_leaf_signals( s ):
    if s.is_sliced_signal(): return []
    if s.is_leaf_signal():   return [ s ]

    leaf_signals = []
    def recursive_getattr( m, instance ):
      for x in instance.__dict__:
        signal = getattr( m, x )
        if signal.is_leaf_signal():
          leaf_signals.append( signal )
        else:
          recursive_getattr( signal, instance.__dict__[x] )

    recursive_getattr( s, s._dsl.type_instance )
    return leaf_signals

  def is_sliced_signal( s ):
    return not s._dsl.slice is None

  def is_top_level_signal( s ):
    return s._dsl.top_level_signal is None

  def get_top_level_signal( s ):
    top = s._dsl.top_level_signal
    return s if top is None else top

  def get_sibling_slices( s ):
    if s._dsl.slice:
      parent = s.get_parent_object()
      ret = parent._dsl.slices.values()
      ret.remove( s )
      return ret
    return []

  def slice_overlap( s, other ):
    assert other.get_parent_object() is s.get_parent_object(), \
      "You are only allowed to pass in a sibling signal."
    return _overlap( s._dsl.slice, other._dsl.slice )

# These three subtypes are for type checking purpose
class Wire( Signal ):
  def inverse( s ):
    return Wire( s._dsl.Type )

class InPort( Signal ):
  def inverse( s ):
    return OutPort( s._dsl.Type )
  def is_input_value_port( s ):
    return True

class OutPort( Signal ):
  def inverse( s ):
    return InPort( s._dsl.Type )
  def is_output_value_port( s ):
    return True

class Interface( NamedObject, Connectable ):

  # FIXME: why are we doing this?
  # Yanghui: I commented this out.
  # @property
  # def Type( s ):
  #   return s._dsl.args

  def inverse( s ):
    s._dsl.inversed = True
    return s

  # Override
  # The same reason as __call__ connection. For s.x = A().inverse(),
  # inverse is executed before setattr, so we need to delay it ...

  def _construct( s ):
    if not s._dsl.constructed:
      s.construct( *s._dsl.args, **s._dsl.kwargs )

      inversed = False
      if hasattr( s._dsl, "inversed" ):
        inversed = s._dsl.inversed

      if inversed:
        for name, obj in s.__dict__.iteritems():
          if not name.startswith("_"):
            if isinstance( obj, Signal ):
              setattr( s, name, obj.inverse() )
            else:
              setattr( s, name, obj )

      s._dsl.constructed = True

  # We move the connect functionality to Component
  # def connect()

  #-----------------------------------------------------------------------
  # Public APIs (only can be called after elaboration)
  #-----------------------------------------------------------------------

  def is_component( s ):
    return False

  def is_signal( s ):
    return False

  def is_interface( s ):
    return True

# CallerPort is connected an exterior method, called by the component's
# update block
# CalleePort exposes the method in the component to outside world

class MethodPort( NamedObject, Connectable ):

  def construct( self, *args, **kwargs ):
    raise NotImplementedError("You can only instantiate Caller/CalleePort.")

  def __call__( self, *args, **kwargs ):
    return self.method( *args, **kwargs )

  def is_component( s ):
    return False

  def is_signal( s ):
    return False

  def is_method_port( s ):
    return False

  def is_interface( s ):
    return False

  def in_non_blocking_interface( s ):
    return s._dsl.in_non_blocking_ifc

class CallerPort( MethodPort ):
  def construct( self, Type=None ):
    self.Type = Type
    self.method = None
    self._dsl.in_non_blocking_ifc = False

  def is_callee_port( s ):
    return False

  def is_caller_port( s ):
    return True

class CalleePort( MethodPort ):
  def construct( self, Type=None, method=None ):
    self.Type = Type
    self.method = method
    self._dsl.in_non_blocking_ifc = False

  def is_callee_port( s ):
    return True

  def is_caller_port( s ):
    return False

class NonBlockingInterface( Interface ):
  def construct( s, *args, **kwargs ):
    raise NotImplementedError("You can only instantiate NonBlockingCaller/NonBlockingCalleeIfc.")

  def __call__( s, *args, **kwargs ):
    return s.method( *args, **kwargs )

  def __str__( s ):
    return s._str_hook()

  def _str_hook( s ):
    return "{}".format( s._dsl.my_name )

class NonBlockingCalleeIfc( NonBlockingInterface ):
  def construct( s, Type=None, method=None, rdy=None ):
    s.Type = Type
    s.method = CalleePort( Type, method )
    s.rdy    = CalleePort( None, rdy )

    s.method._dsl.in_non_blocking_ifc = True
    s.rdy._dsl.in_non_blocking_ifc    = True

    s.method._dsl.is_rdy = False
    s.rdy._dsl.is_rdy    = True

class NonBlockingCallerIfc( NonBlockingInterface ):

  def construct( s, Type=None ):
    s.Type = Type

    s.method = CallerPort( Type )
    s.rdy    = CallerPort()

    s.method._dsl.in_non_blocking_ifc = True
    s.rdy._dsl.in_non_blocking_ifc    = True

    s.method._dsl.is_rdy = False
    s.rdy._dsl.is_rdy    = True