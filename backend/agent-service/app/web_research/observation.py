"""Optional diagnostics must not change research execution or trigger retries."""


def emit(observer, event, payload):
    if observer is not None:
        try:
            observer(event, payload)
        except Exception:
            # The recorder's missing terminal marker makes incomplete traces visible.
            pass
