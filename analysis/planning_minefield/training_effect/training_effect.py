from pathlib import Path
import runpy


TARGET = Path(__file__).resolve().parents[2] / "training_effect" / "planning_minefield" / "training_effect.py"


if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
