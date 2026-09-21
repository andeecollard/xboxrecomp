"""
Self-check for is_jump_table_operand: the producer and the consumer must agree.

Run: python3 tools/recomp/test_jump_table_operand.py

lifter.py resolves BOTH indexed forms -- `jmp [reg*scale + table]` and
`jmp [reg + table]` -- and its docstring has said so all along. The CFG
recovery in translator.py, which is the only thing that DISCOVERS tables and
feeds them to the lifter, tested `not operand.mem_index or operand.mem_base`:
it demanded an index register and rejected anything carrying a base.

So the base form was discoverable by nothing and resolvable by code that was
already written. Every `jmp [reg + table]` became an unresolved indirect
branch, and the tail-call fallback that stands in for one is exactly what a
control-flow completeness audit counts as a hole.

The narrow test appeared TWICE in translator.py -- once at the function-level
gate deciding whether to attempt CFG recovery at all, and once in the scan
itself -- so a fix to either alone would have left the other rejecting.

Both now import the predicate from the module that owns it. These checks fail
if that stops being true.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.recomp.lifter import is_jump_table_operand  # noqa: E402


class _Op:
    """Minimal duck-typed memory operand."""
    def __init__(self, disp=0, index=None, base=None):
        self.type = "mem"
        self.mem_disp = disp
        self.mem_index = index
        self.mem_base = base


TABLE = 0x00401000


def test_indexed_form_is_a_jump_table():
    #  jmp [eax*4 + 0x401000] -- the form that already worked
    assert is_jump_table_operand(_Op(disp=TABLE, index="eax"))


def test_base_form_is_a_jump_table():
    #  jmp [eax + 0x401000] -- the form the discovery pass used to reject.
    #  This is the regression this test exists for.
    assert is_jump_table_operand(_Op(disp=TABLE, base="eax")), \
        "base-form tables are resolvable by the lifter and must be discoverable"


def test_base_and_index_together_is_a_jump_table():
    #  jmp [ebx + eax*4 + 0x401000]
    assert is_jump_table_operand(_Op(disp=TABLE, index="eax", base="ebx"))


def test_no_displacement_is_not_a_jump_table():
    #  jmp [eax] is an indirect branch through a pointer, not a table: there
    #  is no base address to read entries from. Requiring the displacement is
    #  what keeps this predicate from swallowing every indirect jump.
    assert not is_jump_table_operand(_Op(index="eax"))
    assert not is_jump_table_operand(_Op(base="eax"))


def test_displacement_alone_is_not_a_jump_table():
    #  jmp [0x401000] is one absolute target, already resolved directly.
    assert not is_jump_table_operand(_Op(disp=TABLE))


def test_producer_and_consumer_use_one_predicate():
    """The actual invariant. The bug was two predicates, not a wrong one."""
    from tools.recomp import translator
    assert translator.is_jump_table_operand is is_jump_table_operand, \
        "translator must import the predicate, not restate it"

    import inspect
    src = inspect.getsource(translator)
    assert "operand.mem_index or operand.mem_base" not in src, \
        "translator has grown its own copy of the predicate again"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("  ok  %s" % fn.__name__)
    print("%d checks passed" % len(fns))


if __name__ == "__main__":
    _run()
