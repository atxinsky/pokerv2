import os
import tempfile
from pathlib import Path

# 单测不打真实 LLM，避免网络和费用
os.environ["POKERGYM_LLM"] = "0"
os.environ["POKERGYM_DB"] = str(Path(tempfile.gettempdir()) / f"pokergym-test-{os.getpid()}.sqlite")
