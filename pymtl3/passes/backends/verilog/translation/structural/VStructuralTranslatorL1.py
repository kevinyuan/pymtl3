#=========================================================================
# VStructuralTranslatorL1.py
#=========================================================================
"""Provide SystemVerilog structural translator implementation."""

from textwrap import dedent

from pymtl3.datatypes import Bits
from pymtl3.passes.backends.generic.structural.StructuralTranslatorL1 import (
    StructuralTranslatorL1,
)
from pymtl3.passes.rtlir import RTLIRDataType as rdt
from pymtl3.passes.rtlir import RTLIRType as rt

from ...errors import VerilogReservedKeywordError
from ...util.utility import get_component_unique_name, make_indent, pretty_concat


class VStructuralTranslatorL1( StructuralTranslatorL1 ):

  def check_decl( s, name, msg ):
    if s.is_verilog_reserved( name ):
      raise VerilogReservedKeywordError( name, msg )

  #-----------------------------------------------------------------------
  # Placeholder
  #-----------------------------------------------------------------------

  def rtlir_tr_placeholder_src( s, m ):
    try:
      if m is s.tr_top:
        # If this placeholder is a top level module, use the wrapper
        # template to support explicit module name.
        if s.tr_cfg.explicit_module_name:
          module_name = s.tr_cfg.explicit_module_name
        else:
          m_rtype = m._pass_structural_rtlir_gen.rtlir_type
          module_name = s.rtlir_tr_component_unique_name(m_rtype)

        pickle_template = dedent(
            '''\
                // This is a wrapper module that wraps PyMTL placeholder {orig_comp_name}
                // This file was generated by PyMTL VerilogPlaceholderPass
                `ifndef {def_symbol}
                `define {def_symbol}

                {pickle_dependency}
                {pickle_wrapper}

                `endif /* {def_symbol} */
            '''
        )

        orig_comp_name = m.config_placeholder.orig_comp_name
        pickle_dependency = m.config_placeholder.pickle_dependency
        pickle_wrapper = \
            m.config_placeholder.pickled_wrapper_template.format(top_module_name = module_name)
        def_symbol = m.config_placeholder.def_symbol

        return pickle_template.format( **locals() )
      else:
        # Otherwise always use the pickled source file
        with open(m.config_placeholder.pickled_source_file, 'r') as fd:
          return fd.read()
    except AttributeError as e:
      # Forgot to apply VerilogPlaceholderPass?
      raise

  #-----------------------------------------------------------------------
  # Data types
  #-----------------------------------------------------------------------

  def rtlir_tr_vector_dtype( s, dtype ):
    msb = dtype.get_length() - 1
    return {
      'def'  : '',
      'nbits' : dtype.get_length(),
      'data_type' : 'logic',
      'packed_type' : f'[{msb}:0]',
      'unpacked_type' : '',
      'raw_dtype' : dtype
    }

  def rtlir_tr_unpacked_array_type( s, Type ):
    if Type is None:
      return { 'def' : '', 'unpacked_type' : '', 'n_dim':[] }
    else:
      array_dim = "".join( f"[0:{size-1}]" for size in Type.get_dim_sizes() )
      return {
        'def'  : '',
        # 'decl' : ' ' + array_dim,
        'unpacked_type' : array_dim,
        'n_dim' : Type.get_dim_sizes()
      }

  #-----------------------------------------------------------------------
  # Declarations
  #-----------------------------------------------------------------------

  def rtlir_tr_port_decls( s, port_decls ):
    make_indent( port_decls, 1 )
    return ',\n'.join( port_decls )

  def rtlir_tr_port_decl( s, id_, Type, array_type, dtype ):
    _dtype = Type.get_dtype()
    direction = Type.get_direction()
    if array_type:
      template = "Note: port {id_} has data type {_dtype}"
    else:
      n_dim = array_type['n_dim']
      template = "Note: {n_dim} array of ports {id_} has data type {_dtype}"
    s.check_decl( id_, template.format( **locals() ) )
    return pretty_concat( direction, dtype['data_type'], dtype['packed_type'],
              id_, array_type['unpacked_type'] )

  def rtlir_tr_wire_decls( s, wire_decls ):
    make_indent( wire_decls, 1 )
    return '\n'.join( wire_decls )

  def rtlir_tr_wire_decl( s, id_, Type, array_type, dtype ):
    _dtype = Type.get_dtype()
    if array_type:
      template = "Note: wire {id_} has data type {_dtype}"
    else:
      n_dim = array_type['n_dim']
      template = "Note: {n_dim} array of wires {id_} has data type {_dtype}"
    s.check_decl( id_, template.format( **locals() ) )
    return pretty_concat( dtype['data_type'], dtype['packed_type'],
              id_, array_type['unpacked_type'], ';' )

  def rtlir_tr_const_decls( s, const_decls ):
    make_indent( const_decls, 1 )
    return '\n'.join( const_decls )

  def gen_array_param( s, n_dim, dtype, array ):
    if not n_dim:
      if isinstance( dtype, rdt.Vector ):
        return s._literal_number( dtype.get_length(), array )
      else:
        assert False, f'{array} is not an integer or a BitStruct!'
    else:
      ret = []
      for _idx, idx in enumerate( range( n_dim[0] ) ):
        ret.append( s.gen_array_param( n_dim[1:], dtype, array[idx] ) )
      return f"'{{ {', '.join(ret)} }}"

  def rtlir_tr_const_decl( s, id_, Type, array_type, dtype, value ):
    _dtype = Type.get_dtype()
    if array_type:
      template = "Note: constant {id_} has data type {_dtype}"
    else:
      n_dim = array_type['n_dim']
      template = "Note: {n_dim} array of constants {id_} has data type {_dtype}"
    s.check_decl( id_, template.format( **locals() ) )
    _dtype = pretty_concat(dtype['packed_type'], id_, array_type['unpacked_type'])
    _value = s.gen_array_param( array_type['n_dim'], dtype['raw_dtype'], value )

    return f'localparam {_dtype} = {_value};'

  #-----------------------------------------------------------------------
  # Connections
  #-----------------------------------------------------------------------

  def rtlir_tr_connections( s, connections ):
    make_indent( connections, 1 )
    return '\n'.join( connections )

  def rtlir_tr_connection( s, wr_signal, rd_signal ):
    return f'assign {rd_signal} = {wr_signal};'

  #-----------------------------------------------------------------------
  # Signal operations
  #-----------------------------------------------------------------------

  def rtlir_tr_bit_selection( s, base_signal, index, status ):
    # Bit selection
    return s._rtlir_tr_process_unpacked(
              f'{base_signal}[{index}]',
              f'{base_signal}{{}}[{index}]',
              status, ('status', 'unpacked') )

  def rtlir_tr_part_selection( s, base_signal, start, stop, status ):
    # Part selection
    return s._rtlir_tr_process_unpacked(
              f'{base_signal}[{stop-1}:{start}]',
              f'{base_signal}{{}}[{stop-1}:{start}]',
              status, ('status', 'unpacked') )

  def rtlir_tr_port_array_index( s, base_signal, index, status ):
    return s._rtlir_tr_process_unpacked(
              f'{base_signal}[{index}]',
              f'{base_signal}{{}}[{index}]',
              status, ('status', 'unpacked') )

  def rtlir_tr_wire_array_index( s, base_signal, index, status ):
    return f'{base_signal}[{index}]'

  def rtlir_tr_const_array_index( s, base_signal, index, status ):
    return f'{base_signal}[{index}]'

  def rtlir_tr_current_comp_attr( s, base_signal, attr, status ):
    return f'{attr}'

  def rtlir_tr_current_comp( s, comp_id, comp_rtype, status ):
    return ''

  def _rtlir_tr_process_unpacked( s, signal, signal_tplt, status, enable ):
    if (status in ('reader', 'writer') and 'status' in enable) or \
       (s._rtlir_tr_unpacked_q and 'unpacked' in enable):
      ret = signal_tplt.format(''.join(
                [f'[{i}]' for i in list(s._rtlir_tr_unpacked_q)]))
      s._rtlir_tr_unpacked_q.clear()
      return ret
    else:
      return signal

  #-----------------------------------------------------------------------
  # Miscs
  #-----------------------------------------------------------------------

  def rtlir_tr_var_id( s, var_id ):
    return var_id.replace( '[', '__' ).replace( ']', '' )

  def _literal_number( s, nbits, value ):
    return f"{nbits}'d{int(value)}"

  def rtlir_tr_literal_number( s, nbits, value, status ):
    return s._literal_number( nbits, value )

  def rtlir_tr_component_unique_name( s, c_rtype ):
    return get_component_unique_name( c_rtype )
