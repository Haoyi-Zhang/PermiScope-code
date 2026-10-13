# Owned receiver-dispatch regression; check/enabled are local recording stubs.
class Guard:
    def enforce(self) -> None:
        self.permission()
        if enabled("dispatch.outer"):
            self.extra()

    def permission(self) -> None:
        check("P_BASE")

    def extra(self) -> None:
        check("P_C")


class GuardA(Guard):
    def permission(self) -> None:
        check("P_A")


class GuardB(Guard):
    def permission(self) -> None:
        check("P_B")


class Box:
    selected: Guard
    other: Guard


class Service:
    def relay(self, value: Guard) -> Guard:
        alias: Guard = value
        return alias

    def run(self) -> None:
        box: Box = Box()
        a: Guard = GuardA()
        b: Guard = GuardB()
        alias: Box = box
        alias.selected = a
        box.other = b
        first: Guard = self.relay(a)
        second: Guard = self.relay(b)
        target: Guard = first
        loaded: Guard = alias.selected
        loaded.enforce()
        target.enforce()
