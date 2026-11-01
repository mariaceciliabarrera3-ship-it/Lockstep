import datetime
import os

from core.orchestrator import ApprovalError, DesignFailed, OutOfScopeError
from core.report import gate_report
from core.wiring import build_orchestrator
from security.secrets import SecretManager


def show(wf):
    print("\nState:", wf.state.value)
    print(gate_report(wf))


def main():
    secrets = SecretManager()
    for name in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
        secrets.load_from_environment(name)

    wired = build_orchestrator("config.json", os.environ, "state", redact=secrets.redact)
    orch = wired.orchestrator
    print("Development Agent - prototype")
    print("MODE:", wired.mode + (f" ({wired.reason})" if wired.reason else ""))

    name = input("Project name: ")
    objective = input("Describe the programming project: ")
    project_id = datetime.datetime.now().strftime("project-%Y%m%d-%H%M%S")

    try:
        wf = orch.start_project(project_id, name, objective)
    except OutOfScopeError as exc:
        print("\nREJECTED:", exc)
        return
    except DesignFailed as exc:
        print("\nDESIGN FAILED (state saved, paused):", exc)
        return

    while True:
        show(wf)
        choice = input("\n[a]pprove / [c]hanges / [r]eject: ").strip().lower()
        try:
            if choice == "a":
                orch.approve(wf)
                orch.begin_implementation(wf)
                print("\nApproved. Implementation phase is not built yet.")
                return
            if choice == "c":
                orch.request_changes(wf, input("What should change? "))
                if wf.state.value == "PAUSED":
                    print("\nToo many revisions. Paused for human review.")
                    return
            elif choice == "r":
                orch.reject(wf)
                print("\nProject rejected.")
                return
        except ApprovalError as exc:
            print("\nNot allowed:", exc)
        except OutOfScopeError as exc:
            print("\nREJECTED:", exc)
        except DesignFailed as exc:
            print("\nDESIGN FAILED (state saved, paused):", exc)
            return


if __name__ == "__main__":
    main()
