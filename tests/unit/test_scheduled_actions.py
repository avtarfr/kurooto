"""Every scheduled action takes the job's payload: the scheduler calls fn(payload), and a method without that argument
failed on every run while its by-hand path (/graph now) worked, so nothing noticed."""

import inspect


def test_every_registered_action_accepts_a_payload(env):
    app = env.app
    for m in list(app.modules.values()):
        try:
            m.start()  # registers its actions and schedules; a feature that can't start here registers what it can
        except Exception:  # noqa: S112 (not set up in a bare test home: its other actions are still checked)
            continue
    assert len(app.scheduler.actions) > 20
    bad = []
    for name, fn in app.scheduler.actions.items():
        try:
            inspect.signature(fn).bind({})
        except TypeError:
            bad.append(name)
        except ValueError:  # a builtin without a signature
            continue
    for m in list(app.modules.values()):
        try:
            m.stop()
        except Exception:  # noqa: S112
            continue
    assert not bad, f"these actions can't take the payload the scheduler passes: {bad}"
