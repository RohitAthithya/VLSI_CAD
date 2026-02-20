from typing import Any
from proj_utils import print_dashed_lines


@print_dashed_lines
def print_output():
    print("hello")


# phase 1: print the fan in and fan out info
class node:
    # each gate is a node

    # input list - multiple fan ins
    def __init__(self):
        self.inputs = list()
        self.outputs = list()

    # output - multiple fan outs


print_output()
