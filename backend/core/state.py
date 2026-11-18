from core.exceptions import BusinessError


def transition(obj, action, transitions):
    target = transitions.get((obj.status, action))
    if target is None:
        raise BusinessError(40902, "This action is not available in the current state")
    obj.status = target
