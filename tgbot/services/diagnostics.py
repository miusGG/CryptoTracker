from pathlib import Path


def error_context(error):
    """Report the failure location without exception text or local variables."""
    context = f"error={type(error).__name__}"
    trace = error.__traceback__
    if trace is not None:
        while trace.tb_next is not None:
            trace = trace.tb_next
        code = trace.tb_frame.f_code
        context += f" source={Path(code.co_filename).name}:{trace.tb_lineno} function={code.co_name}"
    if isinstance(error, OSError) and error.errno is not None:
        context += f" errno={error.errno}"
    return context
