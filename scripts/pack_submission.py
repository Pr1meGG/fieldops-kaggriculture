#!/usr/bin/env python3
"""
scripts/pack_submission.py — Package and verify submission.tar.gz for Kaggle.
"""

import os
import sys
import tarfile
import tempfile
import shutil
from kaggle_environments import make

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSION_TAR = os.path.join(ROOT_DIR, "submission.tar.gz")

def _filter_pycache(tarinfo):
    if "__pycache__" in tarinfo.name or tarinfo.name.endswith(".pyc"):
        return None
    return tarinfo

def pack_submission():
    print(f"Building {SUBMISSION_TAR}...")
    with tarfile.open(SUBMISSION_TAR, "w:gz") as tar:
        # Add main.py at root of tar
        tar.add(os.path.join(ROOT_DIR, "main.py"), arcname="main.py", filter=_filter_pycache)
        
        # Add fieldops package directly at root of tar (flat layout)
        src_fieldops = os.path.join(ROOT_DIR, "src", "fieldops")
        tar.add(src_fieldops, arcname="fieldops", filter=_filter_pycache)
        
    print(f"Archive created successfully. Size: {os.path.getsize(SUBMISSION_TAR)} bytes.")

def verify_submission():
    print("Verifying submission archive in clean isolated environment...")
    temp_dir = tempfile.mkdtemp(prefix="fieldops_sub_test_")
    try:
        # Extract archive into isolated temp_dir
        with tarfile.open(SUBMISSION_TAR, "r:gz") as tar:
            tar.extractall(path=temp_dir)
            
        main_py = os.path.join(temp_dir, "main.py")
        assert os.path.exists(main_py), "main.py missing from archive!"
        assert os.path.exists(os.path.join(temp_dir, "fieldops", "__init__.py")), "fieldops package missing from archive root!"
        
        # Ensure src/ directory DOES NOT exist in temp_dir to simulate Kaggle environment
        assert not os.path.exists(os.path.join(temp_dir, "src")), "src/ directory should not exist in isolated test environment!"
        
        # Run test episode with Kaggle environment runner in temp_dir as CWD
        orig_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            env = make("kaggriculture", debug=True)
            steps = env.run([main_py, "pass"])
        finally:
            os.chdir(orig_cwd)
        
        final_step = steps[-1]
        status = final_step[0].status
        reward = final_step[0].reward
        
        assert status == "DONE" or status == "ACTIVE", f"Unexpected run status: {status}"
        assert reward is not None and reward > 20000, f"Unexpected reward: {reward}"
        
        print(f"Verification PASSED! Status: {status}, Final Reward: ${reward:,.2f}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    pack_submission()
    verify_submission()
