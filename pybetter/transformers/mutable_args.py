from itertools import takewhile, tee, dropwhile
from typing import Union, Dict, List

import libcst as cst
from libcst import matchers as m
from libcst.helpers import parse_template_statement

from pybetter.transformers.base import NoqaAwareTransformer


def is_docstring(node):
    return m.matches(node, m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())]))


class ArgEmptyInitTransformer(NoqaAwareTransformer):
    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:
        modified_defaults: List = []
        mutable_args: Dict[cst.Name, Union[cst.List, cst.Dict]] = {}

        for default_param in original_node.params.params:
            if isinstance(default_param.default, (cst.List, cst.Dict)):
                mutable_args[default_param.name] = default_param.default.deep_clone()
                modified_defaults.append(
                    default_param.with_changes(default=cst.Name("None"))
                )
            else:
                modified_defaults.append(default_param)

        modified_params: cst.Parameters = original_node.params.with_changes(
            params=modified_defaults
        )

        initializations: List[cst.SimpleStatementLine] = [
            parse_template_statement(
                """
if {arg} is None:
    {arg} = {init}
""",
                arg=arg,
                init=init,
            )
            for arg, init in mutable_args.items()
        ]

        docstrings = takewhile(is_docstring, original_node.body.body)
        function_code = dropwhile(is_docstring, original_node.body.body)

        modified_body = (*docstrings, *initializations, *function_code)

        return updated_node.with_changes(
            params=modified_params,
            body=original_node.body.with_changes(body=modified_body),
        )
