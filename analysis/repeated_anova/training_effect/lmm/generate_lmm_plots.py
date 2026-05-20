from pathlib import Path
import runpy


TARGET = Path(__file__).resolve().parents[3] / "training_effect" / "generate_plots.py"


if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
