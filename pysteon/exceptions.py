"""
Exception classes.
"""

class CommandFailure(RuntimeError):
    """
    An INSTEON command reported a failure.
    """

    def __init__(self, command_code):
        self.command_code = command_code
        super().__init__("INSTEON command 0x%02x failed" % command_code.value)
