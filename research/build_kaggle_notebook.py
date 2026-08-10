import json

REPOSITORY_URL = "https://github.com/Pr1meGG/fieldops-kaggriculture.git"
INFRASTRUCTURE_COMMIT = "40032f1b4e5321306e273c21d4dec1f4eba1aea0"
CANDIDATE_COMMIT = "499d043e81041152b1422e95cb1515a6d0476b8a"
CHAMPION_COMMIT = "1b05b9b6e4932e6bdf8a01497cf94cfbbd9aa61f"
RUNNER_PATH = "research/benchmark_runner.py"


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.splitlines()],
    }


notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Kaggriculture — isolated frozen benchmark environment\n",
                "\n",
                "This notebook uses separate, immutable checkouts for benchmark infrastructure, "
                "the A-v2 candidate, and Champion. It does not run a benchmark until all pre-flight "
                "and smoke-test checks pass.\n",
            ],
        },
        code_cell(
            "# 1. Create three independent, detached, immutable checkouts\n"
            "from pathlib import Path\n"
            "import shutil\n"
            "import subprocess\n"
            "\n"
            f"REPOSITORY_URL = {REPOSITORY_URL!r}\n"
            f"INFRASTRUCTURE_COMMIT = {INFRASTRUCTURE_COMMIT!r}\n"
            f"CANDIDATE_COMMIT = {CANDIDATE_COMMIT!r}\n"
            f"CHAMPION_COMMIT = {CHAMPION_COMMIT!r}\n"
            f"RUNNER_PATH = {RUNNER_PATH!r}\n"
            "WORKING = Path('/kaggle/working')\n"
            "INFRASTRUCTURE = WORKING / 'benchmarkinfrastructure'\n"
            "CANDIDATE = WORKING / 'candidate'\n"
            "CHAMPION = WORKING / 'champion'\n"
            "\n"
            "def run(*args):\n"
            "    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()\n"
            "\n"
            "def checkout(destination, commit):\n"
            "    if destination.exists():\n"
            "        shutil.rmtree(destination)\n"
            "    # Fetch all advertised refs only to obtain the immutable commit below.\n"
            "    run('git', 'clone', '--no-single-branch', REPOSITORY_URL, str(destination))\n"
            "    run('git', '-C', str(destination), 'checkout', '--detach', commit)\n"
            "    actual = run('git', '-C', str(destination), 'rev-parse', 'HEAD')\n"
            "    assert actual == commit, f'{destination.name} HEAD {actual} != {commit}'\n"
            "\n"
            "checkout(INFRASTRUCTURE, INFRASTRUCTURE_COMMIT)\n"
            "checkout(CANDIDATE, CANDIDATE_COMMIT)\n"
            "checkout(CHAMPION, CHAMPION_COMMIT)\n"
            "\n"
            "# The harness is sourced by Git from the frozen candidate tree, where its exact blob lives.\n"
            "# This adds no candidate agent code to the infrastructure checkout and leaves its HEAD pinned.\n"
            "run('git', '-C', str(INFRASTRUCTURE), 'checkout', CANDIDATE_COMMIT, '--', RUNNER_PATH)\n"
            "expected_runner_blob = run('git', '-C', str(INFRASTRUCTURE), 'rev-parse',\n"
            "                          f'{CANDIDATE_COMMIT}:{RUNNER_PATH}')\n"
            "actual_runner_blob = run('git', '-C', str(INFRASTRUCTURE), 'hash-object',\n"
            "                         str(INFRASTRUCTURE / RUNNER_PATH))\n"
            "assert actual_runner_blob == expected_runner_blob, 'benchmark runner blob mismatch'\n"
            "print('Created isolated benchmarkinfrastructure/, candidate/, and champion/ checkouts.')"
        ),
        code_cell(
            "# 2. Immutable checkout pre-flight: fail before any seed can execute\n"
            "expected_heads = {\n"
            "    'infrastructure': (INFRASTRUCTURE, INFRASTRUCTURE_COMMIT),\n"
            "    'candidate': (CANDIDATE, CANDIDATE_COMMIT),\n"
            "    'champion': (CHAMPION, CHAMPION_COMMIT),\n"
            "}\n"
            "for label, (directory, expected) in expected_heads.items():\n"
            "    actual = run('git', '-C', str(directory), 'rev-parse', 'HEAD')\n"
            "    print(f'{label} HEAD = {actual}')\n"
            "    assert actual == expected, f'{label} HEAD {actual} != {expected}'\n"
            "\n"
            "assert (INFRASTRUCTURE / RUNNER_PATH).is_file(), 'benchmark_runner.py is missing'\n"
            "assert (CANDIDATE / 'src/fieldops/agent.py').is_file(), 'candidate agent is missing'\n"
            "assert (CHAMPION / 'src/fieldops/agent.py').is_file(), 'champion agent is missing'\n"
            "print('PRE-FLIGHT PASS — no benchmark seed has executed.')"
        ),
        code_cell(
            "# 3. Kaggle-authoritative engine pre-flight: use the preinstalled runtime only\n"
            "import kaggle_environments\n"
            "from kaggle_environments import make\n"
            "\n"
            "EXPECTED_ENGINE_MODULE_VERSION = '1.32.6'\n"
            "EXPECTED_ENGINE_SPEC_VERSION = '0.1.0'\n"
            "CONFIGURATION_FINGERPRINT = {\n"
            "    'episodeSteps': 720,\n"
            "    'townCenterSellInterval': 24,\n"
            "    'farmHandCostMult': 1,\n"
            "    'townShopSellInterval': 4,\n"
            "    'townShopUnlockInterval': 3,\n"
            "    'turnsPerDay': 24,\n"
            "    'marketParams': {},\n"
            "}\n"
            "\n"
            "# `seed` is explicit for deterministic initialization; it is intentionally not part\n"
            "# of the public configuration fingerprint because the engine records it in env.info.\n"
            "engine_config = {**CONFIGURATION_FINGERPRINT, 'seed': 1}\n"
            "print(f'kaggle_environments.__version__ = {kaggle_environments.__version__}')\n"
            "environment = make('kaggriculture', debug=False, configuration=engine_config)\n"
            "assert environment is not None, 'Kaggriculture environment did not initialize'\n"
            "environment_json = environment.toJSON()\n"
            "\n"
            "assert kaggle_environments.__version__ == EXPECTED_ENGINE_MODULE_VERSION, (\n"
            "    f'kaggle_environments.__version__={kaggle_environments.__version__}, '\n"
            "    f'expected {EXPECTED_ENGINE_MODULE_VERSION}'\n"
            ")\n"
            "assert environment_json['module_version'] == EXPECTED_ENGINE_MODULE_VERSION, (\n"
            "    f'env module_version={environment_json[\"module_version\"]}, '\n"
            "    f'expected {EXPECTED_ENGINE_MODULE_VERSION}'\n"
            ")\n"
            "assert environment.version == EXPECTED_ENGINE_SPEC_VERSION, (\n"
            "    f'env spec version={environment.version}, expected {EXPECTED_ENGINE_SPEC_VERSION}'\n"
            ")\n"
            "actual_fingerprint = {\n"
            "    key: getattr(environment.configuration, key)\n"
            "    for key in CONFIGURATION_FINGERPRINT\n"
            "}\n"
            "assert actual_fingerprint == CONFIGURATION_FINGERPRINT, (\n"
            "    f'engine configuration {actual_fingerprint} != {CONFIGURATION_FINGERPRINT}'\n"
            ")\n"
            "assert environment.info['seed'] == 1, 'engine did not retain the explicit seed'\n"
            "print('ENGINE PRE-FLIGHT PASS — Kaggle runtime matches the authoritative baseline.')"
        ),
        code_cell(
            "# 4. Mandatory zero-seed smoke test and immutable manifest\n"
            "import importlib\n"
            "import importlib.util\n"
            "import json\n"
            "import sys\n"
            "\n"
            "runner_spec = importlib.util.spec_from_file_location(\n"
            "    'benchmark_runner_smoke', INFRASTRUCTURE / RUNNER_PATH\n"
            ")\n"
            "runner_module = importlib.util.module_from_spec(runner_spec)\n"
            "runner_spec.loader.exec_module(runner_module)\n"
            "assert callable(runner_module.run_experiment), 'benchmark runner did not import'\n"
            "\n"
            "def import_isolated_agent(label, source_root):\n"
            "    for name in list(sys.modules):\n"
            "        if name == 'fieldops' or name.startswith('fieldops.'):\n"
            "            del sys.modules[name]\n"
            "    sys.path.insert(0, str(source_root))\n"
            "    try:\n"
            "        module = importlib.import_module('fieldops.agent')\n"
            "        assert Path(module.__file__).resolve().is_relative_to(source_root.resolve())\n"
            "        assert callable(module.agent), f'{label} agent is not callable'\n"
            "        print(f'{label} agent import: {module.__file__}')\n"
            "    finally:\n"
            "        sys.path.remove(str(source_root))\n"
            "\n"
            "import_isolated_agent('candidate', CANDIDATE / 'src')\n"
            "import_isolated_agent('champion', CHAMPION / 'src')\n"
            "\n"
            "BENCHMARK_MANIFEST = {\n"
            "    'candidate_sha': CANDIDATE_COMMIT,\n"
            "    'champion_sha': CHAMPION_COMMIT,\n"
            "    'infrastructure_sha': INFRASTRUCTURE_COMMIT,\n"
            "    'benchmark_runner_blob': actual_runner_blob,\n"
            "    'kaggle_environments_version': kaggle_environments.__version__,\n"
            "    'env_module_version': environment_json['module_version'],\n"
            "    'env_spec_version': environment.version,\n"
            "    'configuration_fingerprint': actual_fingerprint,\n"
            "}\n"
            "print(json.dumps(BENCHMARK_MANIFEST, indent=2, sort_keys=True))\n"
            "PREFLIGHT_COMPLETE = True\n"
            "print('DRY-RUN PASS — runner and both agents imported; 0 seeds run.')"
        ),
        code_cell(
            "# 5. Benchmark A-v2 candidate against frozen Champion (50 seeds)\n"
            "# HARD STOP: this cell fails unless every preceding pre-flight completed successfully.\n"
            "assert PREFLIGHT_COMPLETE is True, 'FATAL: complete all pre-flight cells before running seeds'\n"
            "!python /kaggle/working/benchmarkinfrastructure/research/benchmark_runner.py \\\n"
            "    --agent-root /kaggle/working/candidate/src \\\n"
            "    --agent fieldops.agent:agent \\\n"
            "    --champion-commit 1b05b9b6e4932e6bdf8a01497cf94cfbbd9aa61f \\\n"
            "    --opponent /kaggle/working/champion/src/fieldops/agent.py \\\n"
            "    --seeds " + " ".join(str(i) for i in range(1, 51)) + " \\\n"
            "    --experiment-name a_v2_vs_champion_50seed \\\n"
            "    --results-dir /kaggle/working/results"
        ),
        code_cell(
            "# 6. Package results (only after the benchmark cell has been intentionally run)\n"
            "!cd /kaggle/working && tar -czvf results.tar.gz results/\n"
            "print('Done! Download results.tar.gz from the output panel.')"
        ),
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "version": "3.10.12",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 4,
}

with open("/media/projects/playground/projects/fieldops/research/kaggle_research.ipynb", "w") as f:
    json.dump(notebook, f, indent=2)

print("kaggle_research.ipynb generated.")
