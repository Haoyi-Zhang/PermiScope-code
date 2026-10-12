# Owned straight-line fixture. check and enabled are supplied by the local runner.
class Guard:
    def enforce(self) -> None:
        return


class GuardA(Guard):
    def enforce(self) -> None:
        check("P_A")


class GuardB(Guard):
    def enforce(self) -> None:
        check("P_B")


class Box:
    selected: Guard
    other: Guard


class Service:
    def relay(self, value: Guard) -> Guard:
        alias: Guard = value
        return alias

    def helper(self) -> None:
        if enabled("opaque.inner"):
            check("P_C")

    def run(self) -> None:
        box: Box = Box()
        a: Guard = GuardA()
        b: Guard = GuardB()
        alias: Box = box
        alias.selected = a
        box.other = b
        first: Guard = self.relay(a)
        second: Guard = self.relay(b)
        target: Guard = second
        loaded: Guard = alias.selected
        loaded.enforce()
        target.enforce()
        if enabled("opaque.outer"):
            self.helper()
