import os

# Avoid optional Xet integration warnings when hf_xet isn't installed.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

