#=========================================================================
# CalleeIfc.py
#=========================================================================
# RTL method interface. RTL equivalence of NonBlockingCalleeIfc in CL
#
# Author : Yixiao Zhang
#   Date : June 10, 2019

from __future__ import absolute_import, division, print_function

from copy import deepcopy

from pymtl3 import *
from pymtl3.dsl.errors import InvalidConnectionError


#-------------------------------------------------------------------------
# CalleeRTL2CL
#-------------------------------------------------------------------------
class CalleeRTL2CL( Component ):

  def construct( s, ifc_rtl_callee ):

    ifc_rtl_caller = deepcopy( ifc_rtl_callee )
    ifc_rtl_caller._dsl.constructed = False
    s.ifc_rtl_caller = ifc_rtl_caller.inverse()

    s.called = False
    s.rdy = False

    # generate upblk depending on args
    if s.ifc_rtl_caller.args:
      # has args, create tmp var
      s.args = s.ifc_rtl_caller.args._dsl.Type()

      # update args & en
      @s.update
      def update_en_args():
        s.ifc_rtl_caller.en = Bits1( 1 ) if s.called else Bits1( 0 )
        s.ifc_rtl_caller.args = s.args
        s.called = False

      # add constraints between callee method and upblk
      s.add_constraints( M( s.cl_callee_method ) < U( update_en_args ) )

      # know which method to add constraints on later
      cl_method = s.cl_callee_method

    else:
      # no args, update en
      @s.update
      def update_en():
        s.ifc_rtl_caller.en = Bits1( 1 ) if s.called else Bits1( 0 )
        s.called = False

      # add constraints between callee method and upblk
      s.add_constraints( M( s.cl_callee_method_no_arg ) < U( update_en ) )

      # know which method to add constraints on later
      cl_method = s.cl_callee_method_no_arg

    # generate upblk depending on rets
    if s.ifc_rtl_caller.rets:
      # create tmp var for rets
      s.rets = s.ifc_rtl_caller.rets._dsl.Type()

      # generate upblk for rets
      @s.update
      def update_rets():
        s.rets = s.ifc_rtl_caller.rets

      s.add_constraints( U( update_rets ) < M( cl_method ) )

    else:
      # return None if no ret
      s.rets = None

    # Generate upblk and add constraints for rdy
    @s.update
    def update_rdy():
      s.rdy = True if s.ifc_rtl_caller.rdy else False

    s.add_constraints( U( update_rdy ) < M( cl_method ) )

  @non_blocking( lambda s: s.rdy )
  def cl_callee_method( s, **kwargs ):
    s.args.__dict__.update( kwargs )
    s.called = True
    return s.rets

  @non_blocking( lambda s: s.rdy )
  def cl_callee_method_no_arg( s ):
    s.called = True
    return s.rets


#-------------------------------------------------------------------------
# CalleeIfcRTL
#-------------------------------------------------------------------------
class CalleeIfcRTL( Interface ):

  def construct( s, ArgTypes=None, RetTypes=None ):
    if ArgTypes:
      # mangle arg bit_struct name by fields
      arg_cls_name = "CalleeIfcRTL_Arg"
      for arg_name, arg_type in ArgTypes:
        arg_cls_name += "_{}_{}".format( arg_name, arg_type.__name__ )

      s.args = InPort( mk_bit_struct( arg_cls_name, ArgTypes ) )

    else:
      s.args = None

    if RetTypes:
      # mangle ret bit_struct name by fields
      ret_cls_name = "CalleeIfcRTL_Ret"
      for ret_name, ret_type in RetTypes:
        ret_cls_name += "__{}_{}".format( ret_name, ret_type.__name__ )

      s.rets = OutPort( mk_bit_struct( ret_cls_name, RetTypes ) )

    else:
      s.rets = None

    s.en = InPort( Bits1 )
    s.rdy = OutPort( Bits1 )

  def connect( s, other, parent ):

    def connect_callee_ifc( this, other ):
      if this.args:
        assert other.args
        parent.connect( other.args, this.args )
      if this.rets:
        assert other.rets
        parent.connect( this.rets, other.rets )

      parent.connect_pairs( this.en, other.en, this.rdy, other.rdy )

    if isinstance( other, CalleeIfcRTL ):
      connect_callee_ifc( s, other )
      return True

    if isinstance( other, NonBlockingCalleeIfc ):
      if s._dsl.level <= other._dsl.level:
        raise InvalidConnectionError(
            "CL2RTL connection is not supported between CalleeIfcRTL"
            " and NonBlockingCalleeIfc.\n"
            "          - level {}: {} (class {})\n"
            "          - level {}: {} (class {})".format(
                s._dsl.level, repr( s ), type( s ), other._dsl.level,
                repr( other ), type( other ) ) )

      rtl2cl_adapter = CalleeRTL2CL( s )

      setattr( parent, "callee_rtl2cl_adapter_" + s._dsl.my_name,
               rtl2cl_adapter )

      connect_callee_ifc( s, rtl2cl_adapter.ifc_rtl_caller )

      if s.args:
        parent.connect( other, rtl2cl_adapter.cl_callee_method )
      else:
        parent.connect( other, rtl2cl_adapter.cl_callee_method_no_arg )

      return True
    return False
